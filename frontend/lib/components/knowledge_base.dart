import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:io';
import 'package:http_parser/http_parser.dart';

class KnowledgeBase extends StatefulWidget {
  final String projectId;

  const KnowledgeBase({Key? key, required this.projectId}) : super(key: key);

  @override
  State<KnowledgeBase> createState() => _KnowledgeBaseState();
}

class _KnowledgeBaseState extends State<KnowledgeBase> {
  List<dynamic> _knowledgeBaseContent = [];
  List<dynamic> _displayedContent = [];
  final TextEditingController _textController = TextEditingController();
  bool _isLoading = true;
  bool _isLoadingMore = false;
  String? _error;
  bool _mounted = true;
  final ScrollController _scrollController = ScrollController();
  final int _itemsPerPage = 10;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _fetchKnowledgeBaseContent();
  }

  @override
  void dispose() {
    _mounted = false;
    _scrollController.dispose();
    _textController.dispose();
    super.dispose();
  }

  void _safeSetState(VoidCallback fn) {
    if (_mounted && mounted) {
      setState(fn);
    }
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent * 0.8) {
      _loadMoreContent();
    }
  }

  void _loadMoreContent() {
    if (_isLoadingMore) return;

    final startIndex = _displayedContent.length;
    if (startIndex >= _knowledgeBaseContent.length) return;

    _safeSetState(() {
      _isLoadingMore = true;
    });

    Future.delayed(const Duration(milliseconds: 500), () {
      if (!_mounted) return;

      final newItems =
          _knowledgeBaseContent.skip(startIndex).take(_itemsPerPage).toList();

      _safeSetState(() {
        _displayedContent.addAll(newItems);
        _isLoadingMore = false;
      });
    });
  }

  Future<void> _fetchKnowledgeBaseContent() async {
    _safeSetState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await http.get(
        Uri.parse('$apiUrl/knowledge-base?project_id=${widget.projectId}'),
        headers: await getAuthHeaders(),
      );

      if (!_mounted) return;

      if (response.statusCode == 200) {
        final content = json.decode(utf8.decode(response.bodyBytes))['content'];
        _safeSetState(() {
          _knowledgeBaseContent = content;
          _displayedContent = content.take(_itemsPerPage).toList();
          _isLoading = false;
        });
      } else {
        _safeSetState(() {
          _error = 'Error fetching knowledge base content';
          _isLoading = false;
        });
        Fluttertoast.showToast(msg: 'Error fetching knowledge base content');
      }
    } catch (error) {
      if (!_mounted) return;
      _safeSetState(() {
        _error = error.toString();
        _isLoading = false;
      });
      print('Error fetching knowledge base content: $error');
      Fluttertoast.showToast(msg: 'Error fetching knowledge base content');
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
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['txt', 'md', 'pdf', 'doc', 'docx'],
        allowMultiple: false,
        withData: true,
      );

      if (result != null && result.files.isNotEmpty) {
        final file = result.files.first;

        if (file.bytes == null) {
          Fluttertoast.showToast(msg: 'Error: Could not read file');
          return;
        }

        if (file.extension?.toLowerCase() == 'txt' ||
            file.extension?.toLowerCase() == 'md') {
          await _uploadTextFile(file);
        } else {
          await _uploadDocumentFile(file);
        }
      }
    } catch (error) {
      print('Error uploading file: $error');
      Fluttertoast.showToast(msg: 'Error uploading file');
    }
  }

  Future<void> _uploadTextFile(PlatformFile file) async {
    try {
      final content = utf8.decode(file.bytes!);
      await _sendToKnowledgeBase(content, file.name, 'text');
    } catch (e) {
      Fluttertoast.showToast(msg: 'Error: File must be a valid text file');
    }
  }

  Future<void> _uploadDocumentFile(PlatformFile file) async {
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$apiUrl/documents/extract?project_id=${widget.projectId}'),
      );

      request.headers.addAll(await getAuthHeaders());

      request.files.add(
        http.MultipartFile.fromBytes(
          'file',
          file.bytes!,
          filename: file.name,
          contentType: MediaType.parse(_getContentType(file.extension ?? '')),
        ),
      );

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final extractedText =
            json.decode(utf8.decode(response.bodyBytes))['text'];
        await _sendToKnowledgeBase(extractedText, file.name, 'document');
      } else {
        Fluttertoast.showToast(msg: 'Error processing document');
      }
    } catch (e) {
      print('Error processing document: $e');
      Fluttertoast.showToast(msg: 'Error processing document');
    }
  }

  Future<void> _sendToKnowledgeBase(
      String content, String filename, String type) async {
    final formData = http.MultipartRequest(
      'POST',
      Uri.parse('$apiUrl/knowledge-base?project_id=${widget.projectId}'),
    );

    formData.headers.addAll(await getAuthHeaders());
    formData.fields['documents'] = content;
    formData.fields['project_id'] = widget.projectId;
    formData.fields['metadata_str'] = json.encode({
      'type': type,
      'filename': filename,
      'project_id': widget.projectId,
    });

    final streamedResponse = await formData.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 200 || response.statusCode == 201) {
      Fluttertoast.showToast(msg: 'File uploaded successfully');
    } else {
      Fluttertoast.showToast(msg: 'Error adding to knowledge base');
    }
  }

  String _getContentType(String extension) {
    switch (extension.toLowerCase()) {
      case 'pdf':
        return 'application/pdf';
      case 'doc':
      case 'docx':
        return 'application/msword';
      case 'txt':
        return 'text/plain';
      case 'md':
        return 'text/markdown';
      default:
        return 'application/octet-stream';
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
      final StringBuffer markdown = StringBuffer();
      markdown.writeln('# Knowledge Base Export\n');

      for (var item in _knowledgeBaseContent) {
        markdown.writeln('## ${item['title'] ?? item['name'] ?? 'Untitled'}\n');
        markdown.writeln('Type: ${item['type']}\n');
        markdown.writeln('${item['content']}\n');
        markdown.writeln('---\n');
      }

      String? outputFile = await FilePicker.platform.saveFile(
        dialogTitle: 'Save Knowledge Base Export',
        fileName: 'knowledge_base_export.md',
        type: FileType.custom,
        allowedExtensions: ['md'],
      );

      if (outputFile != null) {
        final file = File(outputFile);
        await file.writeAsString(markdown.toString());
        Fluttertoast.showToast(msg: 'Knowledge base exported successfully');
      }
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
                  'Showing ${_displayedContent.length} of ${_knowledgeBaseContent.length} items',
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
                    onPressed: () => _handleFileUpload(context),
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
          controller: _scrollController,
          padding: const EdgeInsets.all(16),
          itemCount: _displayedContent.length + (_isLoadingMore ? 1 : 0),
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) {
            if (index == _displayedContent.length) {
              return _buildLoadingIndicator();
            }
            return _buildContentItem(_displayedContent[index]);
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

  Widget _buildLoadingIndicator() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16),
      alignment: Alignment.center,
      child: const CircularProgressIndicator(),
    );
  }
}
