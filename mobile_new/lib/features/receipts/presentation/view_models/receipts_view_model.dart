import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/network/api_client.dart';
import '../../data/models/receipt.dart';
import '../../data/services/receipts_service.dart';

final _receiptsServiceProvider = Provider<ReceiptsService>(
  (ref) => ReceiptsService(ref.watch(apiClientProvider)),
);

final receiptsProvider =
    AsyncNotifierProvider<ReceiptsNotifier, List<ReceiptJob>>(
        ReceiptsNotifier.new);

class ReceiptsNotifier extends AsyncNotifier<List<ReceiptJob>> {
  @override
  Future<List<ReceiptJob>> build() =>
      ref.read(_receiptsServiceProvider).fetchReceipts();

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(_receiptsServiceProvider).fetchReceipts(),
    );
  }

  Future<void> delete(String jobId) async {
    final current = state.value;
    if (current == null) return;

    // Optimistic remove
    state = AsyncData(current.where((r) => r.jobId != jobId).toList());

    try {
      await ref.read(_receiptsServiceProvider).deleteReceipt(jobId);
    } catch (_) {
      // Restore on failure
      state = await AsyncValue.guard(
        () => ref.read(_receiptsServiceProvider).fetchReceipts(),
      );
      rethrow;
    }
  }

  Future<void> edit(
    String jobId, {
    String? vendor,
    String? receiptDate,
    List<Map<String, String>>? items,
  }) async {
    final updated = await ref.read(_receiptsServiceProvider).editReceipt(
          jobId,
          vendor: vendor,
          receiptDate: receiptDate,
          items: items,
        );
    final current = state.value;
    if (current == null) return;
    state = AsyncData([
      for (final r in current)
        if (r.jobId == jobId) updated else r,
    ]);
  }
}
