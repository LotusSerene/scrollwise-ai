import 'package:flutter/material.dart';

class Header extends StatelessWidget implements PreferredSizeWidget {
  final bool isLoggedIn;
  final VoidCallback onLogout;
  final bool isGenerating;

  const Header({
    Key? key,
    required this.isLoggedIn,
    required this.onLogout,
    required this.isGenerating,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFF212529),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // Navigation links
          if (isLoggedIn)
            Expanded(
              child: Row(
                children: [
                  _buildNavLink(context, 'Create', '/create'),
                  _buildNavLink(context, 'Editor', '/editor'),
                  _buildNavLink(context, 'Dashboard', '/dashboard'),
                  _buildNavLink(context, 'Validity', '/validity'),
                  _buildNavLink(context, 'Knowledge Base', '/knowledge-base'),
                  _buildNavLink(context, 'Settings', '/settings'),
                  _buildNavLink(context, 'Query', '/query'), // Added Query link
                ],
              ),
            ),
          // Login/Logout button
          TextButton(
            onPressed: isLoggedIn
                ? onLogout
                : () => Navigator.pushNamed(context, '/login'),
            child: Text(
              isLoggedIn ? 'Logout' : 'Login',
              style: const TextStyle(color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNavLink(BuildContext context, String title, String route) {
    return TextButton(
      onPressed:
          isGenerating ? null : () => Navigator.pushNamed(context, route),
      child: Text(title, style: const TextStyle(color: Colors.white)),
    );
  }

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);
}
