import 'dart:io';
import 'dart:isolate';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../../core/config/app_config.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/storage/capture_file_repository.dart';
import '../../data/models/upload_job.dart';
import '../../data/services/upload_service.dart';

final _uploadServiceProvider = Provider<UploadService>(
  (ref) => UploadService(ref.watch(apiClientProvider)),
);

/// Holds filenames that were skipped due to exceeding the size limit.
/// Cleared by the UI after display via [ref.listen].
final oversizedWarningsProvider = StateProvider<List<String>>((ref) => []);

final uploadProvider =
    NotifierProvider<UploadNotifier, List<PhotoUpload>>(UploadNotifier.new);

class UploadNotifier extends Notifier<List<PhotoUpload>> {
  @override
  List<PhotoUpload> build() => [];

  UploadService get _service => ref.read(_uploadServiceProvider);
  CaptureFileRepository get _fileRepo => ref.read(captureFileRepositoryProvider);

  void _warnOversized(List<String> names) {
    if (names.isEmpty) return;
    ref.read(oversizedWarningsProvider.notifier).update((s) => [...s, ...names]);
  }

  Future<void> pickPhotos() async {
    final picker = ImagePicker();
    final files = await picker.pickMultiImage(imageQuality: 90);
    if (files.isEmpty) return;

    final tooBig = <String>[];
    final newUploads = <PhotoUpload>[];

    for (final file in files) {
      final bytes = await file.readAsBytes();
      if (bytes.length > AppConfig.maxFileSizeBytes) {
        tooBig.add(file.name);
        continue;
      }
      newUploads.add(PhotoUpload(
        id: '${file.name}_${DateTime.now().microsecondsSinceEpoch}',
        filePath: file.path,
      ));
    }

    state = [...state, ...newUploads];
    _warnOversized(tooBig);
  }

  Future<void> takePhoto() async {
    final picker = ImagePicker();
    final file = await picker.pickImage(source: ImageSource.camera, imageQuality: 90);
    if (file == null) return;

    final dir = await _fileRepo.getSavedDir();
    final ts = DateTime.now().millisecondsSinceEpoch;
    final savedPath = '${dir.path}/receipt_$ts.jpg';
    await File(file.path).copy(savedPath);

    final bytes = await File(savedPath).readAsBytes();
    if (bytes.length > AppConfig.maxFileSizeBytes) {
      _warnOversized(['receipt_$ts.jpg']);
      return;
    }

    state = [
      ...state,
      PhotoUpload(id: 'camera_$ts', filePath: savedPath),
    ];
  }

  Future<List<File>> getSavedCaptures() => _fileRepo.listSavedCaptures();

  Future<void> addSavedCaptures(List<File> files) async {
    final tooBig = <String>[];
    final newUploads = <PhotoUpload>[];
    final currentPaths = state.map((u) => u.filePath).toSet();

    for (final file in files) {
      if (currentPaths.contains(file.path)) continue;
      final bytes = await file.readAsBytes();
      if (bytes.length > AppConfig.maxFileSizeBytes) {
        tooBig.add(file.uri.pathSegments.last);
        continue;
      }
      newUploads.add(PhotoUpload(
        id: '${file.uri.pathSegments.last}_${DateTime.now().microsecondsSinceEpoch}',
        filePath: file.path,
      ));
    }

    state = [...state, ...newUploads];
    _warnOversized(tooBig);
  }

  void remove(String id) {
    state = state.where((u) => u.id != id).toList();
  }

  void clearCompleted() {
    state = state.where((u) => !u.isDone).toList();
  }

  Future<void> uploadAll() async {
    final pending = state.where((u) => u.status == UploadStatus.idle).toList();
    await Future.wait(pending.map((u) => _uploadOne(u.id)));
  }

  Future<void> _uploadOne(String id) async {
    _update(id, (u) => u.copyWith(status: UploadStatus.uploading));

    try {
      final filePath = _findById(id).filePath;
      final contentType = UploadService.contentTypeFor(filePath);

      final bytes = await File(filePath).readAsBytes();
      final imageHash = await Isolate.run(
        () => sha256.convert(bytes).toString(),
      );

      final (:jobId, :uploadUrl) = await _service.requestUploadUrl(
        contentType,
        imageHash: imageHash,
      );

      _update(id, (u) => u.copyWith(jobId: jobId));

      await _service.uploadToS3(uploadUrl, Uint8List.fromList(bytes), contentType);

      _update(id, (u) => u.copyWith(status: UploadStatus.processing));

      final result = await _service.pollJob(jobId);

      if (result == null) {
        _update(id, (u) => u.copyWith(
              status: UploadStatus.failed,
              error: 'Processing timed out.',
            ));
        return;
      }

      if (result.isDuplicate) {
        _update(id, (u) => u.copyWith(
              status: UploadStatus.duplicate,
              error: 'This image has already been scanned.',
            ));
        return;
      }

      if (result.isFailed) {
        _update(id, (u) => u.copyWith(
              status: UploadStatus.failed,
              error: 'Processing failed.',
            ));
        return;
      }

      _update(id, (u) => u.copyWith(
            status: UploadStatus.complete,
            result: result,
          ));

      try {
        await _fileRepo.moveToProcessed(jobId, filePath);
      } catch (_) {
        // Non-fatal — photo stays in active folder if move fails
      }
    } on DuplicateImageException {
      _update(id, (u) => u.copyWith(
            status: UploadStatus.duplicate,
            error: 'Already scanned.',
          ));
    } on Exception catch (e) {
      _update(id, (u) => u.copyWith(
            status: UploadStatus.failed,
            error: e.toString(),
          ));
    }
  }

  PhotoUpload _findById(String id) => state.firstWhere((u) => u.id == id);

  void _update(String id, PhotoUpload Function(PhotoUpload) transform) {
    state = [
      for (final u in state)
        if (u.id == id) transform(u) else u
    ];
  }
}
