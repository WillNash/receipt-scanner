import 'dart:io';

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
              padding: const EdgeInsets.only(bottom: 140),
              itemCount: uploads.length,
              itemBuilder: (context, i) => _UploadTile(
                upload: uploads[i],
                onRemove: () => notifier.remove(uploads[i].id),
              ),
            ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      floatingActionButton: _BottomActions(
        hasIdle: hasIdle,
        onCamera: () async {
          await notifier.takePhoto();
          _consumeWarnings(context, notifier);
        },
        onGallery: () async {
          await notifier.pickPhotos();
          _consumeWarnings(context, notifier);
        },
        onSaved: () => _showSavedCapturesPicker(context, notifier),
        onUpload: notifier.uploadAll,
      ),
    );
  }

  void _consumeWarnings(BuildContext context, UploadNotifier notifier) {
    final warnings = notifier.consumeOversizedWarnings();
    if (warnings.isNotEmpty && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('${warnings.length} file(s) skipped — over 20 MB limit.'),
        ),
      );
    }
  }

  Future<void> _showSavedCapturesPicker(
      BuildContext context, UploadNotifier notifier) async {
    final selected = await showModalBottomSheet<List<File>>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => _SavedCapturesPicker(notifier: notifier),
    );
    if (selected != null && selected.isNotEmpty) {
      await notifier.addSavedCaptures(selected);
      if (context.mounted) _consumeWarnings(context, notifier);
    }
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
          Icon(Icons.camera_alt_outlined, size: 64),
          SizedBox(height: 16),
          Text('Take a photo or pick receipts from your gallery.'),
        ],
      ),
    );
  }
}

class _BottomActions extends StatelessWidget {
  const _BottomActions({
    required this.hasIdle,
    required this.onCamera,
    required this.onGallery,
    required this.onSaved,
    required this.onUpload,
  });

  final bool hasIdle;
  final VoidCallback onCamera;
  final VoidCallback onGallery;
  final VoidCallback onSaved;
  final VoidCallback onUpload;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _TrayButton(
                icon: Icons.camera_alt,
                label: 'Camera',
                onPressed: onCamera,
              ),
              _TrayButton(
                icon: Icons.photo_library,
                label: 'Gallery',
                onPressed: onGallery,
              ),
              _TrayButton(
                icon: Icons.folder_special,
                label: 'Saved',
                onPressed: onSaved,
              ),
            ],
          ),
          if (hasIdle) ...[
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
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

class _TrayButton extends StatelessWidget {
  const _TrayButton({
    required this.icon,
    required this.label,
    required this.onPressed,
  });

  final IconData icon;
  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.primary;
    return InkWell(
      onTap: onPressed,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: color,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SavedCapturesPicker extends StatefulWidget {
  const _SavedCapturesPicker({required this.notifier});
  final UploadNotifier notifier;

  @override
  State<_SavedCapturesPicker> createState() => _SavedCapturesPickerState();
}

class _SavedCapturesPickerState extends State<_SavedCapturesPicker> {
  List<File>? _files;
  final Set<String> _selected = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final files = await widget.notifier.getSavedCaptures();
    if (mounted) setState(() => _files = files);
  }

  @override
  Widget build(BuildContext context) {
    final files = _files;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Row(
            children: [
              Text(
                'Saved captures',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Spacer(),
              if (files != null && files.isNotEmpty)
                FilledButton(
                  onPressed: _selected.isEmpty
                      ? null
                      : () {
                          final picked = files
                              .where((f) => _selected.contains(f.path))
                              .toList();
                          Navigator.of(context).pop(picked);
                        },
                  child: Text(
                    _selected.isEmpty ? 'Select images' : 'Add (${_selected.length})',
                  ),
                ),
            ],
          ),
        ),
        const Divider(height: 1),
        if (files == null)
          const Padding(
            padding: EdgeInsets.all(40),
            child: CircularProgressIndicator(),
          )
        else if (files.isEmpty)
          const Padding(
            padding: EdgeInsets.all(40),
            child: Text('No saved captures yet. Tap "Camera" to take a photo.'),
          )
        else
          Flexible(
            child: GridView.builder(
              shrinkWrap: true,
              padding: const EdgeInsets.all(8),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 3,
                crossAxisSpacing: 4,
                mainAxisSpacing: 4,
              ),
              itemCount: files.length,
              itemBuilder: (context, i) {
                final file = files[i];
                final isSelected = _selected.contains(file.path);
                return GestureDetector(
                  onTap: () => setState(() {
                    if (isSelected) {
                      _selected.remove(file.path);
                    } else {
                      _selected.add(file.path);
                    }
                  }),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.file(file, fit: BoxFit.cover),
                      if (isSelected)
                        Container(
                          color: Colors.black38,
                          alignment: Alignment.topRight,
                          padding: const EdgeInsets.all(4),
                          child: const Icon(
                            Icons.check_circle,
                            color: Colors.white,
                            size: 20,
                          ),
                        ),
                    ],
                  ),
                );
              },
            ),
          ),
        SizedBox(height: MediaQuery.of(context).padding.bottom + 8),
      ],
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
