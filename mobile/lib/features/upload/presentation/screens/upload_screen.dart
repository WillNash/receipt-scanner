import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/upload_job.dart';
import '../view_models/upload_view_model.dart';

class UploadScreen extends ConsumerWidget {
  const UploadScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final uploads = ref.watch(uploadProvider);
    final notifier = ref.read(uploadProvider.notifier);
    final hasIdle = uploads.any((u) => u.status == UploadStatus.idle);
    final hasDone = uploads.any((u) => u.isDone);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Upload'),
        actions: [
          if (hasDone)
            TextButton(
              onPressed: notifier.clearCompleted,
              child: const Text('Clear done'),
            ),
        ],
      ),
      body: uploads.isEmpty
          ? const _EmptyState()
          : ListView.builder(
              padding: const EdgeInsets.only(bottom: 100),
              itemCount: uploads.length,
              itemBuilder: (context, i) => _UploadTile(
                upload: uploads[i],
                onRemove: () => notifier.remove(uploads[i].id),
              ),
            ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      floatingActionButton: _BottomActions(
        hasIdle: hasIdle,
        onPick: () async {
          await notifier.pickPhotos();
          final warnings = notifier.consumeOversizedWarnings();
          if (warnings.isNotEmpty && context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                    '${warnings.length} file(s) skipped — over 20 MB limit.'),
              ),
            );
          }
        },
        onUpload: notifier.uploadAll,
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.photo_library_outlined, size: 64),
          SizedBox(height: 16),
          Text('Tap "Pick photos" to choose receipts from your gallery.'),
        ],
      ),
    );
  }
}

class _BottomActions extends StatelessWidget {
  const _BottomActions({
    required this.hasIdle,
    required this.onPick,
    required this.onUpload,
  });

  final bool hasIdle;
  final VoidCallback onPick;
  final VoidCallback onUpload;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        children: [
          Expanded(
            child: OutlinedButton.icon(
              onPressed: onPick,
              icon: const Icon(Icons.photo_library),
              label: const Text('Pick photos'),
            ),
          ),
          if (hasIdle) ...[
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton.icon(
                onPressed: onUpload,
                icon: const Icon(Icons.upload),
                label: const Text('Upload'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _UploadTile extends StatelessWidget {
  const _UploadTile({required this.upload, required this.onRemove});

  final PhotoUpload upload;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      child: ListTile(
        leading: _statusIcon(theme),
        title: Text(
          upload.filename,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: _subtitle(theme),
        trailing: upload.status == UploadStatus.idle
            ? IconButton(
                icon: const Icon(Icons.close),
                onPressed: onRemove,
              )
            : null,
      ),
    );
  }

  Widget _statusIcon(ThemeData theme) {
    return switch (upload.status) {
      UploadStatus.idle => const Icon(Icons.image_outlined),
      UploadStatus.uploading => const SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      UploadStatus.processing => const SizedBox(
          width: 24,
          height: 24,
          child:
              CircularProgressIndicator(strokeWidth: 2, color: Colors.orange),
        ),
      UploadStatus.complete =>
        const Icon(Icons.check_circle, color: Colors.green),
      UploadStatus.failed =>
        const Icon(Icons.error_outline, color: Colors.red),
    };
  }

  Widget? _subtitle(ThemeData theme) {
    return switch (upload.status) {
      UploadStatus.idle => null,
      UploadStatus.uploading => const Text('Uploading…'),
      UploadStatus.processing => const Text('Processing with Textract…'),
      UploadStatus.failed => Text(
          upload.error ?? 'Upload failed.',
          style: TextStyle(color: theme.colorScheme.error),
        ),
      UploadStatus.complete => Text(
          [
            if (upload.result?.vendor != null) upload.result!.vendor!,
            if (upload.result?.total != null) 'Total: ${upload.result!.total}',
          ].join('  ·  '),
        ),
    };
  }
}
