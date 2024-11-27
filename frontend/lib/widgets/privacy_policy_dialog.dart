import 'package:flutter/material.dart';

class PrivacyPolicyDialog extends StatelessWidget {
  const PrivacyPolicyDialog({super.key});

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Privacy Policy'),
      content: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Last updated: 26.03.2024',
              style: TextStyle(fontStyle: FontStyle.italic),
            ),
            const SizedBox(height: 16),
            const Text(
              'At ScrollWise AI, we prioritize the protection of your privacy and personal information. This Privacy Policy outlines how we collect, use, and safeguard your data when using our application.',
            ),
            const SizedBox(height: 16),
            _buildSection(
              'Information We Collect',
              'We collect and process the following types of information:\n'
                  '• Account information (email address, username)\n'
                  '• Writing content (chapters, stories, projects)\n'
                  '• AI-generated content (suggestions, analysis)\n'
                  '• Project settings and preferences\n'
                  '• Vector embeddings of your content for AI processing',
            ),
            _buildSection(
              'How We Use Your Information',
              'Your information is used to:\n'
                  '• Provide our writing assistance services\n'
                  '• Generate and manage story content\n'
                  '• Create and maintain vector embeddings for AI analysis\n'
                  '• Process your writing through AI models\n'
                  '• Save your preferences and settings',
            ),
            _buildSection(
              'Data Storage and Security',
              'We implement industry-standard security measures to protect your data. Your content is stored securely using encryption, and we regularly update our security practices to maintain data protection.',
            ),
            _buildSection(
              'AI Processing',
              'Our application uses artificial intelligence to process your writing. While we strive to maintain privacy, please be mindful that AI processing involves sending your content to our secure servers and third-party AI providers.',
            ),
            _buildSection(
              'Your Rights',
              'You have the right to:\n'
                  '• Access your personal data\n'
                  '• Request data correction or deletion\n'
                  '• Export your content\n'
                  '• Opt-out of certain data processing\n'
                  '• Withdraw consent at any time',
            ),
            _buildSection(
              'Changes to Policy',
              'We may update this Privacy Policy as our services evolve. Significant changes will be notified through the application, and continued use after changes constitutes acceptance.',
            ),
            _buildSection(
              'Contact Us',
              'Sadly, we do not have a contact email yet.',
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          child: const Text('Close'),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ],
    );
  }

  Widget _buildSection(String title, String content) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 16),
        Text(
          title,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        Text(content),
      ],
    );
  }
}
