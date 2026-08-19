import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../view_models/receipts_view_model.dart';
import '../widgets/receipt_card.dart';

class ReceiptsScreen extends ConsumerWidget {
  const ReceiptsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final receiptsAsync = ref.watch(receiptsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('History'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.read(receiptsProvider.notifier).refresh(),
          ),
        ],
      ),
      body: receiptsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48),
              const SizedBox(height: 12),
              Text('Failed to load receipts'),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: () => ref.read(receiptsProvider.notifier).refresh(),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
        data: (receipts) {
          if (receipts.isEmpty) {
            return const Center(
              child: Text('No receipts yet. Upload one!'),
            );
          }
          return RefreshIndicator(
            onRefresh: () => ref.read(receiptsProvider.notifier).refresh(),
            child: ListView.builder(
              itemCount: receipts.length,
              itemBuilder: (context, i) {
                final job = receipts[i];
                return Dismissible(
                  key: ValueKey(job.jobId),
                  direction: DismissDirection.endToStart,
                  background: Container(
                    alignment: Alignment.centerRight,
                    padding: const EdgeInsets.only(right: 20),
                    color: Colors.red.shade700,
                    child: const Icon(Icons.delete_outline, color: Colors.white),
                  ),
                  confirmDismiss: (_) => showDialog<bool>(
                    context: context,
                    builder: (ctx) => AlertDialog(
                      title: const Text('Delete receipt?'),
                      content: const Text(
                        'This permanently deletes the receipt, scan data, and all line items.',
                      ),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(ctx, false),
                          child: const Text('Cancel'),
                        ),
                        FilledButton(
                          onPressed: () => Navigator.pop(ctx, true),
                          style: FilledButton.styleFrom(
                            backgroundColor: Colors.red.shade700,
                          ),
                          child: const Text('Delete'),
                        ),
                      ],
                    ),
                  ),
                  onDismissed: (_) async {
                    try {
                      await ref.read(receiptsProvider.notifier).delete(job.jobId);
                    } catch (_) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Failed to delete receipt.')),
                        );
                      }
                    }
                  },
                  child: ReceiptCard(job: job),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
