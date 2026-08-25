class LineItem {
  const LineItem({
    required this.description,
    this.quantity,
    this.packageSize,
    this.unitPrice,
    this.price,
    this.discount,
    this.itemCategory,
    this.novaGroup,
  });

  final String description;
  final String? quantity;
  final String? packageSize;
  final String? unitPrice;
  final String? price;
  final String? discount;
  final String? itemCategory;
  final int? novaGroup;

  factory LineItem.fromJson(Map<String, dynamic> json) => LineItem(
        description: json['description'] as String? ?? '',
        quantity: json['quantity'] as String?,
        packageSize: json['package_size'] as String?,
        unitPrice: json['unit_price'] as String?,
        price: json['price'] as String?,
        discount: json['discount'] as String?,
        itemCategory: json['item_category'] as String?,
        novaGroup: json['nova_group'] as int?,
      );
}

class ReceiptJob {
  const ReceiptJob({
    required this.jobId,
    required this.status,
    required this.createdAt,
    this.vendor,
    this.receiptDate,
    this.total,
    this.items = const [],
    this.updatedAt,
    this.storeCategory,
    this.priceCheckWarning = false,
    this.priceCheckMessage,
  });

  final String jobId;
  final String status;
  final String createdAt;
  final String? vendor;
  final String? receiptDate;
  final String? total;
  final List<LineItem> items;
  final String? updatedAt;
  final String? storeCategory;
  final bool priceCheckWarning;
  final String? priceCheckMessage;

  bool get isComplete => status == 'COMPLETE';
  bool get isFailed => status == 'FAILED';
  bool get isPending => status == 'PENDING';
  bool get isDuplicate => status == 'DUPLICATE';

  factory ReceiptJob.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return ReceiptJob(
      jobId: json['jobId'] as String,
      status: json['status'] as String,
      createdAt: json['createdAt'] as String? ?? '',
      vendor: json['vendor'] as String?,
      receiptDate: json['receiptDate'] as String?,
      total: json['total'] as String?,
      items: rawItems
          .map((e) => LineItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      updatedAt: json['updatedAt'] as String?,
      storeCategory: json['storeCategory'] as String?,
      priceCheckWarning: json['priceCheckWarning'] as bool? ?? false,
      priceCheckMessage: json['priceCheckMessage'] as String?,
    );
  }
}
