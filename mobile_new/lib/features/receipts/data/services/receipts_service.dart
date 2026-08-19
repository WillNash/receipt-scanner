import 'package:dio/dio.dart';

import '../../../../core/config/app_config.dart';
import '../models/receipt.dart';

class ReceiptsService {
  const ReceiptsService(this._dio);

  final Dio _dio;

  Future<List<ReceiptJob>> fetchReceipts() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '${AppConfig.apiBaseUrl}/receipts',
    );
    final raw = response.data!['receipts'] as List<dynamic>;
    return raw
        .map((e) => ReceiptJob.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<void> deleteReceipt(String jobId) async {
    await _dio.delete<void>('${AppConfig.apiBaseUrl}/receipts/$jobId');
  }
}
