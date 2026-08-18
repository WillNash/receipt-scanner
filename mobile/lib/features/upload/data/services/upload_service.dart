import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../../../../core/config/app_config.dart';
import '../../../receipts/data/models/receipt.dart';

class UploadService {
  UploadService(this._apiDio) : _s3Dio = Dio();

  final Dio _apiDio;
  // Separate Dio for S3 — must NOT include the Authorization header.
  final Dio _s3Dio;

  Future<({String jobId, String uploadUrl})> requestUploadUrl(
    String contentType,
  ) async {
    final response = await _apiDio.post<Map<String, dynamic>>(
      '${AppConfig.apiBaseUrl}/upload-url',
      data: {'contentType': contentType},
    );
    final body = response.data!;
    return (
      jobId: body['jobId'] as String,
      uploadUrl: body['uploadUrl'] as String,
    );
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

      if (job.status == 'COMPLETE' || job.status == 'FAILED') return job;
    }
    return null; // timed out
  }

  static String contentTypeFor(String filePath) {
    final ext = '.${filePath.split('.').last.toLowerCase()}';
    return ext == '.png' ? 'image/png' : 'image/jpeg';
  }
}
