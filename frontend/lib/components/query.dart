import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:logging/logging.dart';

final _logger = Logger('Query');

class Query extends StatefulWidget {
  final String projectId;

  const Query({Key? key, required this.projectId}) : super(key: key);

  @override
  State<Query> createState() => _QueryState();
}

class _QueryState extends State<Query> {
  final TextEditingController _queryController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    final appState = Provider.of<AppState>(context, listen: false);

    // Initialize with saved state
    if (appState.queryState['lastQuery'] != null) {
      _queryController.text = appState.queryState['lastQuery'];
    }

    _loadChatHistory();
  }

  Future<void> _loadChatHistory() async {
    final appState = Provider.of<AppState>(context, listen: false);

    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse(
            '$apiUrl/projects/${widget.projectId}/knowledge-base/chat-history?project_id=${widget.projectId}'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        final jsonResponse = json.decode(utf8.decode(response.bodyBytes));
        final chatHistory =
            List<Map<String, dynamic>>.from(jsonResponse['chatHistory']);
        appState.updateQueryProgress(chatHistory: chatHistory);
      }
    } catch (error) {
      // Handle error
    }
  }

  Future<void> _saveChatHistory() async {
    final appState = Provider.of<AppState>(context, listen: false);
    try {
      final headers = await getAuthHeaders();
      headers['Content-Type'] = 'application/json';
      await http.post(
        Uri.parse(
            '$apiUrl/projects/${widget.projectId}/knowledge-base/chat-history?project_id=${widget.projectId}'),
        headers: headers,
        body: utf8.encode(json.encode({
          'chatHistory': appState.queryState['chatHistory'],
        })),
      );
    } catch (error) {
      // Handle error
    }
  }

  Future<void> _submitQuery() async {
    if (_queryController.text.isEmpty) return;

    final appState = Provider.of<AppState>(context, listen: false);
    final currentHistory = List<Map<String, dynamic>>.from(
        appState.queryState['chatHistory'] ?? []);
    final userMessage = {'type': 'human', 'content': _queryController.text};

    // Update state immediately with user message
    appState.updateQueryProgress(
      isLoading: true,
      chatHistory: [...currentHistory, userMessage],
      lastQuery: _queryController.text,
    );

    try {
      final headers = await getAuthHeaders();
      headers['Content-Type'] = 'application/json';
      final response = await http.post(
        Uri.parse(
            '$apiUrl/projects/${widget.projectId}/knowledge-base/query?project_id=${widget.projectId}'),
        headers: headers,
        body: utf8.encode(json.encode({
          'query': _queryController.text,
          'chatHistory': appState.queryState['chatHistory'],
        })),
      );

      if (response.statusCode == 200) {
        final jsonResponse = json.decode(utf8.decode(response.bodyBytes));
        final newHistory = List<Map<String, dynamic>>.from([
          ...appState.queryState['chatHistory'],
          {'type': 'ai', 'content': jsonResponse['response']},
        ]);

        appState.updateQueryProgress(
          isLoading: false,
          chatHistory: newHistory,
          lastQuery: '',
        );
        _queryController.clear();

        // Add this to scroll to bottom after updating
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (_scrollController.hasClients) {
            _scrollController.animateTo(
              _scrollController.position.maxScrollExtent,
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeOut,
            );
          }
        });

        // Save chat history
        await _saveChatHistory();
      } else {
        // Keep the user message even if the request fails
        appState.updateQueryProgress(
          isLoading: false,
          chatHistory: [...currentHistory, userMessage],
        );
      }
    } catch (error) {
      // Keep the user message even if the request fails
      appState.updateQueryProgress(
        isLoading: false,
        chatHistory: [...currentHistory, userMessage],
      );
    }
  }

  Future<void> _resetChatHistory() async {
    final appState = Provider.of<AppState>(context, listen: false);

    try {
      final headers = await getAuthHeaders();
      await http.post(
        Uri.parse(
            '$apiUrl/projects/${widget.projectId}/knowledge-base/reset-chat-history?project_id=${widget.projectId}'),
        headers: headers,
      );
      appState.updateQueryProgress(
        chatHistory: [],
        lastQuery: null,
      );
    } catch (error) {
      // Handle error
    }
  }

  Widget _buildChatArea() {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        final chatHistory = appState.queryState['chatHistory'] ?? [];

        if (chatHistory.isEmpty) {
          return const Center(
            child: Text('Start a conversation by asking a question'),
          );
        }

        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: ListView.builder(
            controller: _scrollController,
            itemCount: chatHistory.length,
            reverse: false,
            itemBuilder: (context, index) {
              final message = chatHistory[index];
              // Ensure we have both type and content
              if (message == null ||
                  message['type'] == null ||
                  message['content'] == null) {
                _logger.severe('Invalid message at index $index: $message');
                return const SizedBox.shrink();
              }
              final isUser = message['type'] == 'human';
              return _buildMessageBubble(message, isUser);
            },
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        return Column(
          children: [
            _buildHeader(),
            Expanded(
              child: _buildChatArea(),
            ),
            _buildInputArea(appState.queryState['isLoading']),
          ],
        );
      },
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(12)),
        boxShadow: [
          BoxShadow(
            color: Theme.of(context).shadowColor.withOpacity(0.1),
            blurRadius: 4,
          ),
        ],
      ),
      child: Row(
        children: [
          Icon(
            Icons.psychology,
            color: Theme.of(context).colorScheme.primary,
            size: 24,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'AI Assistant',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                Text(
                  'Ask questions about your story',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context)
                            .colorScheme
                            .onSurface
                            .withOpacity(0.6),
                      ),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _resetChatHistory,
            tooltip: 'Reset conversation',
          ),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(Map<String, dynamic> message, bool isUser) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            CircleAvatar(
              backgroundColor: Theme.of(context).colorScheme.primary,
              radius: 16,
              child: const Icon(Icons.psychology, color: Colors.white),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: isUser
                    ? Theme.of(context).colorScheme.primary
                    : Theme.of(context).colorScheme.surface,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(isUser ? 16 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 16),
                ),
                boxShadow: [
                  BoxShadow(
                    color: Theme.of(context).shadowColor.withOpacity(0.1),
                    blurRadius: 4,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Text(
                message['content'],
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: isUser
                          ? Colors.white
                          : Theme.of(context).colorScheme.onSurface,
                    ),
              ),
            ),
          ),
          if (isUser) ...[
            const SizedBox(width: 8),
            CircleAvatar(
              backgroundColor: Theme.of(context).colorScheme.secondary,
              radius: 16,
              child: const Icon(Icons.person, color: Colors.white),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildInputArea(bool isLoading) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
        boxShadow: [
          BoxShadow(
            color: Theme.of(context).shadowColor.withOpacity(0.1),
            blurRadius: 4,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Column(
        children: [
          if (isLoading)
            LinearProgressIndicator(
              backgroundColor:
                  Theme.of(context).colorScheme.surfaceContainerHighest,
              valueColor: AlwaysStoppedAnimation<Color>(
                Theme.of(context).colorScheme.primary,
              ),
            ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _queryController,
                  enabled: !isLoading,
                  decoration: InputDecoration(
                    hintText: 'Ask a question...',
                    filled: true,
                    fillColor:
                        Theme.of(context).colorScheme.surfaceContainerHighest,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(24),
                      borderSide: BorderSide.none,
                    ),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 20,
                      vertical: 12,
                    ),
                  ),
                  onSubmitted:
                      isLoading ? null : (_) => _submitQuery(), // Add this line
                  maxLines: null,
                ),
              ),
              const SizedBox(width: 8),
              FloatingActionButton(
                onPressed: isLoading ? null : _submitQuery,
                child: Icon(
                  isLoading ? Icons.hourglass_empty : Icons.send,
                  color: Colors.white,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _queryController.dispose();
    _scrollController.dispose();
    super.dispose();
  }
}
