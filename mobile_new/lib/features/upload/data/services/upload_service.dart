import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../../../../core/config/app_config.dart';
import '../../../receipts/data/models/receipt.dart';
import '../models/upload_job.dart';

class UploadService {
  UploadService(this._apiDio)
      : _s3Dio = Dio(BaseOptions(
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 30),
        ));

  final Dio _apiDio;
  // Separate Dio for S3 — must NOT include the Authorization header.
  final Dio _s3Dio;

  Future<({String jobId, String uploadUrl})> requestUploadUrl(
    String contentType, {
    String? imageHash,
  }) async {
    try {
      final response = await _apiDio.post<Map<String, dynamic>>(
        '${AppConfig.apiBaseUrl}/upload-url',
        data: {
          'contentType': contentType,
          if (imageHash != null) 'imageHash': imageHash,
        },
      );
      final body = response.data!;
      return (
        jobId: body['jobId'] as String,
        uploadUrl: body['uploadUrl'] as String,
      );
    } on DioException catch (e) {
      if (e.response?.statusCode == 409) {
        throw const DuplicateImageException();
      }
      rethrow;
    }
  }

  Future<void> uploadToS3(
    String presignedUrl,
    Uint8List bytes,
    String contentType,
  ) async {
    await _s3Dio.put<void>(
      presignedUrl,
      data: bytes,
      options: Options(
        contentType: contentType,
        headers: {'Content-Length': bytes.length},
        sendTimeout: const Duration(minutes: 2),
      ),
    );
  }

  Future<ReceiptJob?> pollJob(String jobId) async {
    for (var i = 0; i < AppConfig.pollMaxAttempts; i++) {
      await Future<void>.delayed(
          Duration(milliseconds: AppConfig.pollIntervalMs));

      final response = await _apiDio.get<Map<String, dynamic>>(
        '${AppConfig.apiBaseUrl}/jobs/$jobId',
      );
      final job = ReceiptJob.fromJson(response.data!);

      if (job.isComplete || job.isFailed || job.isDuplicate) return job;
    }
    return null; // timed out
  }

  static String contentTypeFor(String filePath) {
    final ext = filePath.split('.').last.toLowerCase();
    if (ext == 'png') return 'image/png';
    if (ext == 'jpg' || ext == 'jpeg') return 'image/jpeg';
    throw ArgumentError('Unsupported file extension: .$ext');
  }
}
