import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

final captureFileRepositoryProvider = Provider<CaptureFileRepository>(
  (_) => CaptureFileRepository(),
);

class CaptureFileRepository {
  static const _folderName = 'receipt-scanner-images';
  static const _processedFolderName = 'processed';

  Future<Directory> getSavedDir() async {
    final docs = await getApplicationDocumentsDirectory();
    final dir = Directory('${docs.path}/$_folderName');
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  Future<Directory> getProcessedDir() async {
    final docs = await getApplicationDocumentsDirectory();
    final dir = Directory('${docs.path}/$_folderName/$_processedFolderName');
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  Future<List<File>> listSavedCaptures() async {
    final dir = await getSavedDir();
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

  /// Moves a saved capture into the processed/ subfolder, prefixed with [jobId].
  /// No-ops if [filePath] is not inside the saved directory.
  Future<void> moveToProcessed(String jobId, String filePath) async {
    final savedDir = await getSavedDir();
    if (!filePath.startsWith(savedDir.path)) return;
    final processedDir = await getProcessedDir();
    final filename = filePath.split('/').last;
    await File(filePath).rename('${processedDir.path}/${jobId}_$filename');
  }

  /// Moves the processed capture for [jobId] back into the saved directory,
  /// stripping the jobId prefix. No-ops if no matching file is found.
  Future<void> restoreFromProcessed(String jobId) async {
    final processedDir = await getProcessedDir();
    if (!await processedDir.exists()) return;
    await for (final entity in processedDir.list()) {
      if (entity is! File) continue;
      final filename = entity.uri.pathSegments.last;
      if (filename.startsWith('${jobId}_')) {
        final savedDir = await getSavedDir();
        final originalName = filename.substring(jobId.length + 1);
        await entity.rename('${savedDir.path}/$originalName');
        break;
      }
    }
  }
}
