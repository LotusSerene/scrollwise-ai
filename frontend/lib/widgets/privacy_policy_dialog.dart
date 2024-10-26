import 'package:flutter/material.dart';

class PrivacyPolicyDialog extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Privacy Policy'),
      content: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Last updated: 26.10.2024',
              style: TextStyle(fontStyle: FontStyle.italic),
            ),
            SizedBox(height: 16),
            Text(
              'At Storyteller, we are committed to protecting your privacy and ensuring the security of your personal information. This Privacy Policy explains how we collect, use, and safeguard your data when you use our application.',
            ),
            SizedBox(height: 16),
            _buildSection(
              'Information We Collect',
              'We collect the following types of information:\n'
                  '• Personal information (email address, username)\n'
                  '• Project and story-related content\n'
                  '• API keys for third-party services\n'
                  '• Usage data and preferences',
            ),
            _buildSection(
              'How We Use Your Information',
              'We use your information to:\n'
                  '• Provide and improve our services\n'
                  '• Generate and manage your story content\n'
                  '• Analyze and process your writing\n'
                  '• Communicate with you about our services',
            ),
            _buildSection(
              'Data Storage and Security',
              'We store your data securely using encryption and follow industry-standard practices to protect your information from unauthorized access or disclosure.',
            ),
            _buildSection(
              'Third-Party Services',
              'We may use third-party services (such as AI models) to process your data. These services are bound by their own privacy policies and our agreements with them.',
            ),
            _buildSection(
              'Your Rights',
              'You have the right to access, correct, or delete your personal information. You can also request a copy of your data or ask us to restrict its processing.',
            ),
            _buildSection(
              'Changes to This Policy',
              'We may update this Privacy Policy from time to time. We will notify you of any changes by posting the new Privacy Policy on this page.',
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
          child: Text('Close'),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ],
    );
  }

  Widget _buildSection(String title, String content) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(height: 16),
        Text(
          title,
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        SizedBox(height: 8),
        Text(content),
      ],
    );
  }
}
