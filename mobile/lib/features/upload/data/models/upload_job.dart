import '../../receipts/data/models/receipt.dart';

enum UploadStatus { idle, uploading, processing, complete, failed }

class PhotoUpload {
  const PhotoUpload({
    required this.id,
    required this.filePath,
    this.status = UploadStatus.idle,
    this.jobId,
    this.result,
    this.error,
  });

  final String id;
  final String filePath;
  final UploadStatus status;
  final String? jobId;
  final ReceiptJob? result;
  final String? error;

  String get filename => filePath.split('/').last;

  bool get isDone =>
      status == UploadStatus.complete || status == UploadStatus.failed;

  PhotoUpload copyWith({
    UploadStatus? status,
    String? jobId,
    ReceiptJob? result,
    String? error,
  }) {
    return PhotoUpload(
      id: id,
      filePath: filePath,
      status: status ?? this.status,
      jobId: jobId ?? this.jobId,
      result: result ?? this.result,
      error: error ?? this.error,
    );
  }
}
