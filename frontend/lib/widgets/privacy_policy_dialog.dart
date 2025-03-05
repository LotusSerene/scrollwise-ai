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
              'Last updated: 05.03.2025',
              style: TextStyle(fontStyle: FontStyle.italic),
            ),
            const SizedBox(height: 16),
            const Text(
              'At ScrollWise AI, we prioritize the protection of your privacy and personal information. This Privacy Policy outlines how we handle your data when using our application, which is designed with a local-first approach.',
            ),
            const SizedBox(height: 16),
            _buildSection(
              'Local-First Application',
              'ScrollWise AI operates primarily on your local device. This means your writing content and project data are stored locally on your device, giving you more control over your information.',
            ),
            _buildSection(
              'API Key Handling',
              'To utilize the AI features, you need to provide your own API key. This API key is stored securely on your local device and is used to directly access the Gemini API. We do not store or have access to your API key.',
            ),
            _buildSection(
              'Information We Collect',
              'We collect and process only the following types of information:\n'
                  '• Account information (email address, username)',
            ),
            _buildSection(
              'How We Use Your Information',
              'Your account information is used to:\n'
                  '• Authenticate and manage your account\n'
                  '• Personalize your experience',
            ),
            _buildSection(
              'Data Storage and Security',
              'Your account information is stored securely. Your writing content and projects are stored locally on your device.',
            ),
            _buildSection(
              'AI Processing',
              'When you use AI features, your writing content is processed by the Gemini API directly using your API key. We do not process or store your writing content on our servers.',
            ),
            _buildSection(
              'Your Rights',
              'You have the right to:\n'
                  '• Access your account data\n'
                  '• Request data correction or deletion\n'
                  '• Opt-out of certain data processing\n'
                  '• Withdraw consent at any time',
            ),
            _buildSection(
              'Changes to Policy',
              'We may update this Privacy Policy as our services evolve. Significant changes will be notified through the application, and continued use after changes constitutes acceptance.',
            ),
            _buildSection(
              'Contact Us',
              'For privacy-related inquiries, please join our Discord server.',
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
