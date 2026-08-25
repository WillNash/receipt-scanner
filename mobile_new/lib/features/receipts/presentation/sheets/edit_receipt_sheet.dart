import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/receipt.dart';
import '../view_models/receipts_view_model.dart';

class EditableItem {
  EditableItem({
    String desc = '',
    String qty = '',
    String packageSize = '',
    String unitPrice = '',
    String price = '',
    String discount = '',
    this.itemCategory,
    this.novaGroup,
  })  : descCtrl = TextEditingController(text: desc),
        qtyCtrl = TextEditingController(text: qty),
        packageSizeCtrl = TextEditingController(text: packageSize),
        unitPriceCtrl = TextEditingController(text: unitPrice),
        priceCtrl = TextEditingController(text: price),
        discountCtrl = TextEditingController(text: discount);

  factory EditableItem.fromLineItem(LineItem item) => EditableItem(
        desc: item.description,
        qty: item.quantity ?? '',
        packageSize: item.packageSize ?? '',
        unitPrice: item.unitPrice ?? '',
        price: item.price ?? '',
        discount: item.discount ?? '',
        itemCategory: item.itemCategory,
        novaGroup: item.novaGroup,
      );

  final TextEditingController descCtrl;
  final TextEditingController qtyCtrl;
  final TextEditingController packageSizeCtrl;
  final TextEditingController unitPriceCtrl;
  final TextEditingController priceCtrl;
  final TextEditingController discountCtrl;
  final String? itemCategory;
  final int? novaGroup;

  void dispose() {
    descCtrl.dispose();
    qtyCtrl.dispose();
    packageSizeCtrl.dispose();
    unitPriceCtrl.dispose();
    priceCtrl.dispose();
    discountCtrl.dispose();
  }

  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{'description': descCtrl.text.trim()};
    final qty = qtyCtrl.text.trim();
    final pkgSize = packageSizeCtrl.text.trim();
    final up = unitPriceCtrl.text.trim();
    final price = priceCtrl.text.trim();
    final discount = discountCtrl.text.trim();
    if (qty.isNotEmpty) map['quantity'] = qty;
    if (pkgSize.isNotEmpty) map['package_size'] = pkgSize;
    if (up.isNotEmpty) map['unit_price'] = up;
    if (price.isNotEmpty) map['price'] = price;
    if (discount.isNotEmpty) map['discount'] = discount;
    if (itemCategory != null) map['item_category'] = itemCategory;
    if (novaGroup != null) map['nova_group'] = novaGroup;
    return map;
  }
}

void showEditSheet(BuildContext context, ReceiptJob job) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
    ),
    builder: (_) => EditReceiptSheet(job: job),
  );
}

class EditReceiptSheet extends ConsumerStatefulWidget {
  const EditReceiptSheet({super.key, required this.job});

  final ReceiptJob job;

  @override
  ConsumerState<EditReceiptSheet> createState() => _EditReceiptSheetState();
}

class _EditReceiptSheetState extends ConsumerState<EditReceiptSheet> {
  late final TextEditingController _vendorCtrl;
  late final TextEditingController _dateCtrl;
  late List<EditableItem> _editItems;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _vendorCtrl = TextEditingController(text: widget.job.vendor ?? '');
    _dateCtrl = TextEditingController(text: widget.job.receiptDate ?? '');
    _editItems = widget.job.items.map(EditableItem.fromLineItem).toList();
  }

  @override
  void dispose() {
    _vendorCtrl.dispose();
    _dateCtrl.dispose();
    for (final item in _editItems) item.dispose();
    super.dispose();
  }

  double? _parseAmount(String s) {
    final cleaned = s.replaceAll(',', '').replaceAll(r'$', '').trim();
    return double.tryParse(cleaned);
  }

  ({double sum, double? total, bool warn}) _priceCheck() {
    var sum = 0.0;
    for (final item in _editItems) {
      final p = _parseAmount(item.priceCtrl.text);
      if (p != null) sum += p;
    }
    sum = double.parse(sum.toStringAsFixed(2));
    final total = _parseAmount(widget.job.total ?? '');
    if (total == null) return (sum: sum, total: null, warn: false);
    final diff = (sum - total).abs();
    final warn = diff >= 0.01 && total > 0;
    return (sum: sum, total: total, warn: warn);
  }

  void _addItem() => setState(() => _editItems.add(EditableItem()));

  void _removeItem(int index) => setState(() {
        _editItems[index].dispose();
        _editItems.removeAt(index);
      });

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await ref.read(receiptsProvider.notifier).edit(
            widget.job.jobId,
            vendor: _vendorCtrl.text.trim(),
            receiptDate: _dateCtrl.text.trim(),
            items: _editItems.map((e) => e.toJson()).toList(),
          );
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to save: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    final check = _priceCheck();

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
          const SizedBox(height: 12),
          Row(
            children: [
              const Expanded(
                child: Text('Line items',
                    style: TextStyle(fontWeight: FontWeight.w500)),
              ),
              TextButton.icon(
                onPressed: _addItem,
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Add item'),
                style: TextButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          ConstrainedBox(
            constraints: BoxConstraints(
              maxHeight: MediaQuery.of(context).size.height * 0.4,
            ),
            child: ListView.separated(
              shrinkWrap: true,
              itemCount: _editItems.length,
              separatorBuilder: (_, __) =>
                  const Divider(height: 20, thickness: 1),
              itemBuilder: (_, i) => _buildItemRow(i),
            ),
          ),
          if (check.total != null) ...[
            const SizedBox(height: 12),
            _buildPriceBar(check),
          ],
          const SizedBox(height: 12),
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

  Widget _buildItemRow(int i) {
    final item = _editItems[i];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: TextField(
                controller: item.descCtrl,
                decoration: const InputDecoration(
                  labelText: 'Description',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 4),
            IconButton(
              icon: const Icon(Icons.close, size: 18, color: Colors.grey),
              onPressed: () => _removeItem(i),
              tooltip: 'Remove item',
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            Expanded(flex: 2, child: _numField(item.qtyCtrl, 'Qty')),
            const SizedBox(width: 4),
            Expanded(flex: 2, child: _textField(item.packageSizeCtrl, 'Pkg size')),
            const SizedBox(width: 4),
            Expanded(flex: 3, child: _numField(item.unitPriceCtrl, 'Unit price')),
            const SizedBox(width: 4),
            Expanded(
              flex: 3,
              child: _numField(
                item.priceCtrl,
                'Price',
                onChanged: (_) => setState(() {}),
              ),
            ),
            const SizedBox(width: 4),
            Expanded(flex: 3, child: _numField(item.discountCtrl, 'Discount')),
          ],
        ),
      ],
    );
  }

  Widget _textField(TextEditingController ctrl, String label) => TextField(
        controller: ctrl,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
          isDense: true,
        ),
      );

  Widget _numField(
    TextEditingController ctrl,
    String label, {
    void Function(String)? onChanged,
  }) =>
      TextField(
        controller: ctrl,
        onChanged: onChanged,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
          isDense: true,
        ),
        keyboardType: const TextInputType.numberWithOptions(
          decimal: true,
          signed: true,
        ),
      );

  Widget _buildPriceBar(({double sum, double? total, bool warn}) check) {
    final total = check.total!;
    final diff = (check.sum - total).abs();
    final isOk = !check.warn;
    final color = isOk ? Colors.green.shade700 : Colors.orange.shade800;
    final bg = isOk ? Colors.green.shade50 : Colors.orange.shade50;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        children: [
          Icon(
            isOk ? Icons.check_circle_outline : Icons.warning_amber_rounded,
            size: 15,
            color: color,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              isOk
                  ? 'Items \$${check.sum.toStringAsFixed(2)} match total \$${total.toStringAsFixed(2)}'
                  : 'Items \$${check.sum.toStringAsFixed(2)} vs total \$${total.toStringAsFixed(2)} (off \$${diff.toStringAsFixed(2)})',
              style: TextStyle(fontSize: 12, color: color),
            ),
          ),
        ],
      ),
    );
  }
}
