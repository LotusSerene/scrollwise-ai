import 'package:flutter/material.dart';
import '../components/settings.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/gestures.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar.large(
            title: const Text('Settings'),
            actions: [
              IconButton(
                icon: const Icon(Icons.help_outline),
                tooltip: 'Help',
                onPressed: () => _showHelpDialog(context),
              ),
            ],
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.settings,
                        size: 32,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(width: 16),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Application Settings',
                            style: Theme.of(context).textTheme.headlineSmall,
                          ),
                          Text(
                            'Customize your experience',
                            style: Theme.of(context)
                                .textTheme
                                .bodyMedium
                                ?.copyWith(
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
                  const SizedBox(height: 32),
                  const Settings(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

void _showHelpDialog(BuildContext context) {
  showDialog(
    context: context,
    builder: (BuildContext context) {
      return Dialog(
        child: Container(
          constraints: const BoxConstraints(maxWidth: 600),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      Icons.help_outline,
                      size: 24,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(width: 16),
                    Text(
                      'Settings Help',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Flexible(
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildHelpSection(
                          context,
                          'Model Selection',
                          'Choose from different models based on your needs:\n\n'
                              '• Gemini-1.5-pro: Best for complex reasoning tasks and long-form content generation.  Offers a larger context window (2M tokens).  More expensive.\n'
                              '• Gemini-1.5-flash: A fast and versatile model suitable for a wide range of tasks. Offers a good balance of speed and capability (1M token context).\n'
                              '• Gemini-1.5-flash-8b: A cost-effective option ideal for high-frequency, less complex tasks.  (1M token context).',
                          Icons.psychology,
                        ),
                        const SizedBox(height: 16),
                        _buildHelpSection(
                          context,
                          'App Settings',
                          'Customize your application preferences here.  These settings control various aspects of the user interface and application behavior.',
                          Icons.settings,
                        ),
                        const SizedBox(height: 16),
                        _buildHelpSection(
                          context,
                          'API Key Security',
                          'Your Google AI API key is encrypted both in transit and at rest using industry-standard encryption techniques. It is never stored in plain text. We use a robust key management system to protect your key from unauthorized access.\n\n'
                              'For maximum security, we strongly recommend using a dedicated API key for this application and not reusing keys across multiple services.\n\n'
                              'You can always revoke/change the API Key at any time from the settings.',
                          Icons.security,
                        ),
                        const SizedBox(height: 8),
                        RichText(
                          text: TextSpan(
                            style: Theme.of(context).textTheme.bodyMedium,
                            children: [
                              const TextSpan(
                                text: 'To get a free key, visit ',
                              ),
                              TextSpan(
                                text: 'Google AI Studio',
                                style: TextStyle(
                                  color: Theme.of(context).colorScheme.primary,
                                  decoration: TextDecoration.underline,
                                ),
                                recognizer: TapGestureRecognizer()
                                  ..onTap = () async {
                                    final Uri url = Uri.parse(
                                        'https://aistudio.google.com/');
                                    if (!await launchUrl(
                                      url,
                                      mode: LaunchMode.externalApplication,
                                      webOnlyWindowName: '_blank',
                                    )) {
                                      if (context.mounted) {
                                        ScaffoldMessenger.of(context)
                                            .showSnackBar(
                                          const SnackBar(
                                            content: Text(
                                                'Could not launch Google AI Studio'),
                                          ),
                                        );
                                      }
                                    }
                                  },
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        _buildHelpSection(
                          context,
                          'Usage Tips',
                          '• Start with the Flash model: It provides a good balance of speed and performance for most tasks.\n'
                              '• Use the Pro model for complex tasks:  The Pro model is best suited for tasks requiring extensive reasoning, long context, or high-quality creative writing.\n'
                              '• Consider Flash-8B for cost-efficiency: This model is a good choice for simple tasks where cost is a primary concern.\n'
                              '• Manage your context:  Be mindful of the token limits of each model to avoid exceeding the context window.  Break down large tasks into smaller, more manageable chunks if necessary.',
                          Icons.tips_and_updates,
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Close'),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    },
  );
}

Widget _buildHelpSection(
  BuildContext context,
  String title,
  String content,
  IconData icon,
) {
  return Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          Icon(
            icon,
            size: 20,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: 8),
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                ),
          ),
        ],
      ),
      const SizedBox(height: 8),
      Text(
        content,
        style: Theme.of(context).textTheme.bodyMedium,
      ),
    ],
  );
}
