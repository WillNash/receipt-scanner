import 'package:flutter/material.dart';

import '../../data/models/receipt.dart';

class ReceiptCard extends StatelessWidget {
  const ReceiptCard({super.key, required this.job});

  final ReceiptJob job;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
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
        trailing: _statusChip(theme),
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
