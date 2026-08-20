import 'package:flutter/material.dart';

import '../../data/models/receipt.dart';

class ReceiptCard extends StatelessWidget {
  const ReceiptCard({super.key, required this.job, this.onDelete});

  final ReceiptJob job;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      child: ExpansionTile(
        tilePadding: const EdgeInsets.only(left: 16, right: 4, top: 4, bottom: 4),
        title: Text(
          job.vendor ?? 'Unknown vendor',
          style: theme.textTheme.titleMedium,
        ),
        subtitle: Text(
          [
            if (job.receiptDate != null) job.receiptDate!,
            if (job.total != null) 'Total: ${job.total}',
          ].join('  ·  '),
          style: theme.textTheme.bodySmall,
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _statusChip(theme),
            const SizedBox(width: 4),
            IconButton(
              icon: Icon(Icons.delete_outline,
                  size: 20, color: theme.colorScheme.error),
              tooltip: 'Delete',
              onPressed: onDelete,
            ),
            const Icon(Icons.expand_more, size: 20),
            const SizedBox(width: 4),
          ],
        ),
        children: [
          if (job.items.isEmpty)
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('No line items extracted.'),
            )
          else
            _ItemsTable(items: job.items),
        ],
      ),
    );
  }

  Widget _statusChip(ThemeData theme) {
    final (label, color) = switch (job.status) {
      'COMPLETE' => ('Done', Colors.green),
      'FAILED' => ('Failed', Colors.red),
      _ => ('Pending', Colors.orange),
    };
    return Chip(
      label: Text(label, style: const TextStyle(fontSize: 11)),
      backgroundColor: color.withOpacity(0.15),
      side: BorderSide(color: color.withOpacity(0.4)),
      padding: EdgeInsets.zero,
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );
  }
}

class _ItemsTable extends StatelessWidget {
  const _ItemsTable({required this.items});

  final List<LineItem> items;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: Column(
        children: [
          const Divider(height: 1),
          const SizedBox(height: 8),
          ...items.map(
            (item) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(
                children: [
                  Expanded(
                    child: Text(item.description,
                        style: theme.textTheme.bodySmall),
                  ),
                  if (item.price != null)
                    Text(item.price!,
                        style: theme.textTheme.bodySmall
                            ?.copyWith(fontWeight: FontWeight.w500)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
