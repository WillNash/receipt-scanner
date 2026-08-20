import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/receipt.dart';
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
              const Text('Failed to load receipts'),
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
                  confirmDismiss: (_) => _confirmDelete(context),
                  onDismissed: (_) => _deleteAndReport(context, ref, job.jobId),
                  child: ReceiptCard(
                    job: job,
                    onDelete: () async {
                      final confirmed = await _confirmDelete(context);
                      if (confirmed == true && context.mounted) {
                        _deleteAndReport(context, ref, job.jobId);
                      }
                    },
                    onEdit: () => _showEditSheet(context, ref, job),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}

Future<bool?> _confirmDelete(BuildContext context) => showDialog<bool>(
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
            style: FilledButton.styleFrom(backgroundColor: Colors.red.shade700),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

Future<void> _deleteAndReport(
    BuildContext context, WidgetRef ref, String jobId) async {
  try {
    await ref.read(receiptsProvider.notifier).delete(jobId);
  } catch (_) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to delete receipt.')),
      );
    }
  }
}

void _showEditSheet(BuildContext context, WidgetRef ref, ReceiptJob job) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
    ),
    builder: (_) => _EditReceiptSheet(job: job, ref: ref),
  );
}

class _EditReceiptSheet extends StatefulWidget {
  const _EditReceiptSheet({required this.job, required this.ref});

  final ReceiptJob job;
  final WidgetRef ref;

  @override
  State<_EditReceiptSheet> createState() => _EditReceiptSheetState();
}

class _EditReceiptSheetState extends State<_EditReceiptSheet> {
  late final TextEditingController _vendorCtrl;
  late final TextEditingController _dateCtrl;
  late final List<TextEditingController> _itemCtrls;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _vendorCtrl = TextEditingController(text: widget.job.vendor ?? '');
    _dateCtrl = TextEditingController(text: widget.job.receiptDate ?? '');
    _itemCtrls = widget.job.items
        .map((it) => TextEditingController(text: it.description))
        .toList();
  }

  @override
  void dispose() {
    _vendorCtrl.dispose();
    _dateCtrl.dispose();
    for (final c in _itemCtrls) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final items = _itemCtrls
          .map((c) => {'description': c.text.trim()})
          .toList();
      await widget.ref.read(receiptsProvider.notifier).edit(
            widget.job.jobId,
            vendor: _vendorCtrl.text.trim(),
            receiptDate: _dateCtrl.text.trim(),
            items: items,
          );
      if (mounted) Navigator.pop(context);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to save changes.')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text('Edit Receipt',
                    style:
                        TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
              ),
              IconButton(
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.pop(context),
              ),
            ],
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _vendorCtrl,
            decoration: const InputDecoration(
              labelText: 'Store / Vendor',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _dateCtrl,
            decoration: const InputDecoration(
              labelText: 'Receipt date',
              hintText: 'e.g. 2024-03-15',
              border: OutlineInputBorder(),
            ),
          ),
          if (_itemCtrls.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text('Line items',
                style: TextStyle(fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            ConstrainedBox(
              constraints: BoxConstraints(
                maxHeight: MediaQuery.of(context).size.height * 0.35,
              ),
              child: ListView.separated(
                shrinkWrap: true,
                itemCount: _itemCtrls.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (_, i) => TextField(
                  controller: _itemCtrls[i],
                  decoration: InputDecoration(
                    labelText: 'Item ${i + 1}',
                    border: const OutlineInputBorder(),
                    isDense: true,
                  ),
                ),
              ),
            ),
          ],
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Save'),
          ),
        ],
      ),
    );
  }
}
