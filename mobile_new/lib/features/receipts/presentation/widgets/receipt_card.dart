import 'package:flutter/material.dart';

import '../../data/models/receipt.dart';

class ReceiptCard extends StatefulWidget {
  const ReceiptCard({super.key, required this.job, this.onDelete, this.onEdit});

  final ReceiptJob job;
  final VoidCallback? onDelete;
  final VoidCallback? onEdit;

  @override
  State<ReceiptCard> createState() => _ReceiptCardState();
}

class _ReceiptCardState extends State<ReceiptCard> {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: ExpansionTile(
        tilePadding: const EdgeInsets.only(left: 16, right: 4, top: 4, bottom: 4),
        onExpansionChanged: (v) => setState(() => _isExpanded = v),
        title: Text(
          widget.job.vendor ?? 'Unknown vendor',
          style: theme.textTheme.titleMedium,
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              [
                if (widget.job.receiptDate != null) widget.job.receiptDate!,
                if (widget.job.total != null) 'Total: ${widget.job.total}',
                if (widget.job.storeCategory != null)
                  widget.job.storeCategory!.replaceAll('_', ' '),
              ].join('  ·  '),
              style: theme.textTheme.bodySmall,
            ),
            if (widget.job.priceCheckWarning)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  widget.job.priceCheckMessage?.isNotEmpty == true
                      ? 'Price check: ${widget.job.priceCheckMessage}'
                      : 'Price check: item prices do not match total',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.error,
                  ),
                ),
              ),
          ],
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: Icon(Icons.delete_outline,
                  size: 20, color: theme.colorScheme.error),
              tooltip: 'Delete',
              onPressed: widget.onDelete,
            ),
            AnimatedRotation(
              turns: _isExpanded ? 0.5 : 0,
              duration: const Duration(milliseconds: 200),
              child: const Icon(Icons.expand_more, size: 20),
            ),
            const SizedBox(width: 4),
          ],
        ),
        children: [
          if (widget.job.items.isEmpty)
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('No line items extracted.'),
            )
          else
            _ItemsTable(items: widget.job.items),
          Padding(
            padding: const EdgeInsets.only(left: 8, right: 8, bottom: 8),
            child: Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                icon: const Icon(Icons.edit_outlined, size: 16),
                label: const Text('Edit'),
                onPressed: widget.onEdit,
              ),
            ),
          ),
        ],
      ),
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
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          [
                            item.description,
                            if (item.quantity != null && item.unitPrice != null)
                              '${item.quantity} @ \$${item.unitPrice}',
                          ].join('  '),
                          style: theme.textTheme.bodySmall,
                        ),
                      ),
                      if (item.price != null)
                        Text(item.price!,
                            style: theme.textTheme.bodySmall
                                ?.copyWith(fontWeight: FontWeight.w500)),
                    ],
                  ),
                  if (item.discount != null)
                    Padding(
                      padding: const EdgeInsets.only(left: 8),
                      child: Text(
                        'Discount: ${item.discount}',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: Colors.green.shade700,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
