import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

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
      // Surface via a returned list so the UI can show a snackbar.
      _oversizedFiles = tooBig;
    }
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
