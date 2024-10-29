import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:file_picker/file_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:io';
import 'package:share_plus/share_plus.dart';

class KnowledgeBase extends StatefulWidget {
  final String projectId;

  const KnowledgeBase({Key? key, required this.projectId}) : super(key: key);

  @override
  State<KnowledgeBase> createState() => _KnowledgeBaseState();
}

class _KnowledgeBaseState extends State<KnowledgeBase> {
  List<dynamic> _knowledgeBaseContent = [];
  final TextEditingController _textController = TextEditingController();
  var _selectedFile;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchKnowledgeBaseContent();
  }

  Future<void> _fetchKnowledgeBaseContent() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/knowledge-base?project_id=${widget.projectId}'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        setState(() {
          _knowledgeBaseContent =
              json.decode(utf8.decode(response.bodyBytes))['content'];
        });
      } else {
        Fluttertoast.showToast(msg: 'Error fetching knowledge base content');
      }
    } catch (error) {
      print('Error fetching knowledge base content: $error');
      Fluttertoast.showToast(msg: 'Error fetching knowledge base content');
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _handleTextSubmit() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    try {
      final headers = <String, String>{
        ...await getAuthHeaders(),
        'Content-Type': 'application/x-www-form-urlencoded',
      };
      final response = await http.post(
        Uri.parse('$apiUrl/knowledge-base/'),
        headers: headers,
        body: {
          'documents': text,
          'metadata_str':
              json.encode({'type': 'text', 'project_id': widget.projectId}),
          'project_id': widget.projectId,
        },
      );
      final jsonResponse = json.decode(response.body);
      if (response.statusCode == 200 && !jsonResponse.containsKey('error')) {
        setState(() {
          _textController.clear();
        });
        _fetchKnowledgeBaseContent();
        Fluttertoast.showToast(msg: 'Text added to knowledge base');
      } else {
        final errorMessage =
            jsonResponse['error'] ?? 'Error adding text to knowledge base';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error adding text to knowledge base: $error');
      Fluttertoast.showToast(msg: 'Error adding text to knowledge base');
    }
  }

  Future<void> _handleFileUpload(BuildContext context) async {
    if (_selectedFile == null) return;

    try {
      final headers = <String, String>{
        ...await getAuthHeaders(),
        'Content-Type': 'multipart/form-data',
      };
      final request = http.MultipartRequest('POST',
          Uri.parse('$apiUrl/knowledge-base?project_id=${widget.projectId}'));
      request.headers.addAll(headers);
      final file =
          await http.MultipartFile.fromPath('file', _selectedFile.path);
      request.files.add(file);
      request.fields['metadata'] = json.encode({
        'type': 'file',
        'filename': _selectedFile.path,
        'project_id': widget.projectId
      });
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);
      final jsonResponse = json.decode(utf8.decode(response.bodyBytes));

      if (response.statusCode == 201 && !jsonResponse.containsKey('error')) {
        setState(() {
          _selectedFile = null;
        });
        _fetchKnowledgeBaseContent();
        Fluttertoast.showToast(msg: 'File uploaded successfully');
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error uploading file';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error uploading file: $error');
      Fluttertoast.showToast(msg: 'Error uploading file');
    }
  }

  Future<void> _handleDelete(String embeddingId) async {
    try {
      final response = await http.delete(
        Uri.parse(
            '$apiUrl/knowledge-base/$embeddingId?project_id=${widget.projectId}'),
        headers: await getAuthHeaders(),
      );
      final jsonResponse = json.decode(response.body);
      if ((response.statusCode == 204 || response.statusCode == 200) &&
          !jsonResponse.containsKey('error')) {
        setState(() {
          _knowledgeBaseContent
              .removeWhere((item) => item['embedding_id'] == embeddingId);
        });
        Fluttertoast.showToast(msg: 'Item deleted from knowledge base');
      } else {
        final errorMessage =
            jsonResponse['error'] ?? 'Error deleting item from knowledge base';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error deleting item from knowledge base: $error');
      Fluttertoast.showToast(msg: 'Error deleting item from knowledge base');
    }
  }

  Future<void> _exportKnowledgeBase() async {
    try {
      // Create markdown content
      final StringBuffer markdown = StringBuffer();
      markdown.writeln('# Knowledge Base Export\n');
      
      for (var item in _knowledgeBaseContent) {
        markdown.writeln('## ${item['title'] ?? item['name'] ?? 'Untitled'}\n');
        markdown.writeln('Type: ${item['type']}\n');
        markdown.writeln('${item['content']}\n');
        markdown.writeln('---\n');
      }

      // Get temporary directory
      final directory = await getApplicationDocumentsDirectory();
      final file = File('${directory.path}/knowledge_base_export.md');
      await file.writeAsString(markdown.toString());

      // Share the file
      await Share.shareXFiles(
        [XFile(file.path)],
        subject: 'Knowledge Base Export',
      );
    } catch (error) {
      print('Error exporting knowledge base: $error');
      Fluttertoast.showToast(msg: 'Error exporting knowledge base');
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildHeader(),
          const SizedBox(height: 24),
          _buildInputSection(),
          const SizedBox(height: 24),
          _buildContentList(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Icon(
              Icons.psychology,
              size: 32,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: 16),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Knowledge Base',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                Text(
                  '${_knowledgeBaseContent.length} items stored',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context)
                            .colorScheme
                            .onSurface
                            .withOpacity(0.6),
                      ),
                ),
              ],
            ),
          ],
        ),
        Row(
          children: [
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _fetchKnowledgeBaseContent,
              tooltip: 'Refresh content',
            ),
            IconButton(
              icon: const Icon(Icons.upload_file),
              onPressed: _exportKnowledgeBase,
              tooltip: 'Export knowledge base',
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildInputSection() {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Add New Content',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _textController,
              decoration: InputDecoration(
                hintText: 'Enter text to add to knowledge base...',
                prefixIcon: const Icon(Icons.text_fields),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                filled: true,
              ),
              maxLines: 3,
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _handleTextSubmit,
                    icon: const Icon(Icons.add),
                    label: const Text('Add Text'),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.all(16),
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () async {
                      final result = await FilePicker.platform.pickFiles();
                      if (result != null) {
                        setState(() {
                          _selectedFile = result.files.single;
                        });
                        _handleFileUpload(context);
                      }
                    },
                    icon: const Icon(Icons.upload_file),
                    label: const Text('Upload Document'),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.all(16),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContentList() {
    if (_error != null) {
      return _buildErrorState();
    }

    if (_knowledgeBaseContent.isEmpty) {
      return _buildEmptyState();
    }

    return Expanded(
      child: Card(
        elevation: 2,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: ListView.separated(
          padding: const EdgeInsets.all(16),
          itemCount: _knowledgeBaseContent.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) {
            final item = _knowledgeBaseContent[index];
            return _buildContentItem(item);
          },
        ),
      ),
    );
  }

  Widget _buildContentItem(dynamic item) {
    final content = item['content'];
    final title = item['title'] ?? item['name'] ?? 'Untitled';
    final type = item['type'];

    return ListTile(
      contentPadding: const EdgeInsets.symmetric(
        horizontal: 16,
        vertical: 12,
      ),
      leading: Icon(
        type == 'file' ? Icons.description : Icons.text_snippet,
        color: Theme.of(context).colorScheme.primary,
      ),
      title: Text(
        title,
        style: Theme.of(context).textTheme.titleMedium,
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 4),
          Text(
            content.length > 100 ? '${content.substring(0, 100)}...' : content,
            style: Theme.of(context).textTheme.bodyMedium,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 4),
          Text(
            'Type: $type',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                ),
          ),
        ],
      ),
      trailing: IconButton(
        icon: const Icon(Icons.delete),
        color: Theme.of(context).colorScheme.error,
        onPressed: () => _showDeleteDialog(item['embedding_id']),
        tooltip: 'Delete item',
      ),
      onTap: () => _showContentDetails(item),
    );
  }

  void _showContentDetails(dynamic item) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(item['title'] ?? item['name'] ?? 'Untitled'),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Type: ${item['type']}',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.primary,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 16),
                Text(item['content']),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Close'),
            ),
          ],
        );
      },
    );
  }

  void _showDeleteDialog(String embeddingId) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Row(
            children: [
              Icon(Icons.warning, color: Theme.of(context).colorScheme.error),
              const SizedBox(width: 8),
              const Text('Delete Item'),
            ],
          ),
          content: const Text(
            'Are you sure you want to delete this item? This action cannot be undone.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Cancel'),
            ),
            ElevatedButton.icon(
              icon: const Icon(Icons.delete),
              label: const Text('Delete'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Theme.of(context).colorScheme.error,
              ),
              onPressed: () {
                Navigator.of(context).pop();
                _handleDelete(embeddingId);
              },
            ),
          ],
        );
      },
    );
  }

  Widget _buildEmptyState() {
    return Expanded(
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.psychology_outlined,
              size: 64,
              color: Theme.of(context).colorScheme.secondary.withOpacity(0.5),
            ),
            const SizedBox(height: 16),
            Text(
              'Knowledge Base Empty',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: Theme.of(context).colorScheme.secondary,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              'Add text or upload documents to get started',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context)
                        .colorScheme
                        .onSurface
                        .withOpacity(0.6),
                  ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.error_outline,
            size: 64,
            color: Theme.of(context).colorScheme.error,
          ),
          const SizedBox(height: 16),
          Text(
            _error!,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Theme.of(context).colorScheme.error,
                ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _fetchKnowledgeBaseContent,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }
}
