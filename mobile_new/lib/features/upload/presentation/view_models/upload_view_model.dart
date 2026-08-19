import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';

import '../../../../core/config/app_config.dart';
import '../../../../core/network/api_client.dart';
import '../../data/models/upload_job.dart';
import '../../data/services/upload_service.dart';

final _uploadServiceProvider = Provider<UploadService>(
  (ref) => UploadService(ref.watch(apiClientProvider)),
);

final uploadProvider =
    NotifierProvider<UploadNotifier, List<PhotoUpload>>(UploadNotifier.new);

class UploadNotifier extends Notifier<List<PhotoUpload>> {
  @override
  List<PhotoUpload> build() => [];

  UploadService get _service => ref.read(_uploadServiceProvider);

  static const _savedFolderName = 'receipt-scanner-images';

  Future<Directory> _getSavedDir() async {
    final docs = await getApplicationDocumentsDirectory();
    final dir = Directory('${docs.path}/$_savedFolderName');
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
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

    if (tooBig.isNotEmpty) {
      _oversizedFiles = tooBig;
    }
  }

  Future<void> takePhoto() async {
    final picker = ImagePicker();
    final file = await picker.pickImage(source: ImageSource.camera, imageQuality: 90);
    if (file == null) return;

    final dir = await _getSavedDir();
    final ts = DateTime.now().millisecondsSinceEpoch;
    final savedPath = '${dir.path}/receipt_$ts.jpg';
    await File(file.path).copy(savedPath);

    final bytes = await File(savedPath).readAsBytes();
    if (bytes.length > AppConfig.maxFileSizeBytes) {
      _oversizedFiles = ['receipt_$ts.jpg'];
      return;
    }

    state = [
      ...state,
      PhotoUpload(id: 'camera_$ts', filePath: savedPath),
    ];
  }

  Future<List<File>> getSavedCaptures() async {
    final dir = await _getSavedDir();
    final entities = await dir.list().toList();
    return entities
        .whereType<File>()
        .where((f) {
          final lower = f.path.toLowerCase();
          return lower.endsWith('.jpg') ||
              lower.endsWith('.jpeg') ||
              lower.endsWith('.png');
        })
        .toList()
      ..sort((a, b) => b.path.compareTo(a.path));
  }

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
    if (tooBig.isNotEmpty) _oversizedFiles = [..._oversizedFiles, ...tooBig];
  }

  List<String> _oversizedFiles = [];

  List<String> consumeOversizedWarnings() {
    final list = _oversizedFiles;
    _oversizedFiles = [];
    return list;
  }

  void remove(String id) {
    state = state.where((u) => u.id != id).toList();
  }

  void clearCompleted() {
    state = state.where((u) => !u.isDone).toList();
  }

  Future<void> uploadAll() async {
    final pending = state.where((u) => u.status == UploadStatus.idle).toList();
    for (final upload in pending) {
      await _uploadOne(upload.id);
    }
  }

  Future<void> _uploadOne(String id) async {
    _update(id, (u) => u.copyWith(status: UploadStatus.uploading));

    try {
      final filePath = _findById(id).filePath;
      final contentType = UploadService.contentTypeFor(filePath);

      final bytes = await File(filePath).readAsBytes();
      final (:jobId, :uploadUrl) =
          await _service.requestUploadUrl(contentType);

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
