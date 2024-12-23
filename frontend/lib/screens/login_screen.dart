import 'package:flutter/material.dart';
import 'package:jwt_decoder/jwt_decoder.dart';
import '../utils/auth.dart';
import '../widgets/privacy_policy_dialog.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/notifications.dart';

class LoginScreen extends StatefulWidget {
  final Function(String) onLogin;

  const LoginScreen({Key? key, required this.onLogin}) : super(key: key);

  @override
  _LoginScreenState createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  bool _isLoading = false;

  Future<void> _handleSubmit() async {
    if (_formKey.currentState!.validate()) {
      setState(() {
        _isLoading = true;
      });

      try {
        final response = await http.post(
          Uri.parse('$apiUrl/auth/signin'),
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: json.encode({
            'email': _emailController.text,
            'password': _passwordController.text,
          }),
        );

        if (response.statusCode == 200) {
          final data = json.decode(response.body);
          final accessToken = data['access_token'];
          final sessionId = data['session_id'];

          if (accessToken == null) {
            throw Exception('No access token received');
          }

          print('Login response received successfully');

          // Initialize session
          await initializeSession(accessToken, sessionId);

          // Verify authentication state
          final isAuthenticated = await verifyAuthState();
          if (!isAuthenticated) {
            print('Authentication verification failed');
            throw Exception('Authentication state verification failed');
          }

          print('Authentication successful, proceeding to projects screen');
          widget.onLogin(accessToken);

          if (mounted) {
            Navigator.pushReplacementNamed(context, '/projects');
          }
        } else {
          final error = json.decode(response.body);
          throw Exception(error['detail'] ?? 'Error logging in');
        }
      } catch (error) {
        print('Login error: $error');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Error: ${error.toString()}'),
              duration: const Duration(seconds: 3),
            ),
          );
        }
      } finally {
        if (mounted) {
          setState(() {
            _isLoading = false;
          });
        }
      }
    }
  }

  Future<void> _handleRegister() async {
    if (_formKey.currentState!.validate()) {
      setState(() {
        _isLoading = true;
      });

      try {
        final response = await http.post(
          Uri.parse('$apiUrl/auth/register'),
          headers: {'Content-Type': 'application/json'},
          body: json.encode({
            'email': _emailController.text,
            'password': _passwordController.text,
          }),
        );

        if (response.statusCode == 201) {
          final data = json.decode(response.body);
          if (data['needs_verification'] == true) {
            AppNotification.show(
              context,
              'Registration successful! Please check your email to verify your account.',
            );
          } else {
            AppNotification.show(
              context,
              'Registration successful! Please wait for admin approval.',
            );
          }
          _emailController.clear();
          _passwordController.clear();
        } else {
          final error = json.decode(response.body);
          AppNotification.show(
            context,
            error['detail'] ?? 'Registration failed',
          );
        }
      } catch (error) {
        print('Registration error: $error');
        AppNotification.show(
          context,
          error.toString(),
        );
      } finally {
        if (mounted) {
          setState(() {
            _isLoading = false;
          });
        }
      }
    }
  }

  Future<bool> verifyAuthState() async {
    try {
      final token = await getAuthToken();
      final sessionId = await getSessionId();

      print('Verifying authentication state');

      if (token == null || sessionId == null) {
        print('Missing token or sessionId');
        return false;
      }

      // Verify token is not expired
      try {
        if (JwtDecoder.isExpired(token)) {
          print('Token is expired');
          return false;
        }

        print('Auth state verified successfully');
        return true;
      } catch (e) {
        print('Error decoding/verifying token: $e');
        return false;
      }
    } catch (e) {
      print('Error verifying auth state: $e');
      return false;
    }
  }

  Future<void> initializeSession(String accessToken, String sessionId) async {
    try {
      print('Initializing session with token and sessionId');

      // Store session ID first
      await setSessionId(sessionId);

      // Don't try to initialize Supabase session directly
      // Just store the access token locally
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('access_token', accessToken);

      // Verify storage
      final storedToken = await getAuthToken();
      final storedSessionId = await getSessionId();

      print('Session initialized successfully');

      if (storedToken == null || storedSessionId == null) {
        throw Exception('Failed to store session credentials');
      }
    } catch (e) {
      print('Error initializing session: $e');
      // Clean up any partial session data
      await removeSessionId();
      throw Exception('Failed to initialize session: $e');
    }
  }

  Future<bool> checkBackendSession() async {
    try {
      final token = await getAuthToken();
      final sessionId = await getSessionId();

      if (token == null || sessionId == null) {
        return false;
      }

      final response = await http.get(
        Uri.parse('$apiUrl/auth/session'),
        headers: {
          'Authorization': 'Bearer $token',
          'X-Session-ID': sessionId,
        },
      );

      return response.statusCode == 200;
    } catch (e) {
      print('Error checking backend session: $e');
      return false;
    }
  }

  Future<String?> getAuthToken() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getString('access_token');
    } catch (e) {
      print('Error getting auth token: $e');
      return null;
    }
  }

  Future<void> removeAuthToken() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('access_token');
    } catch (e) {
      print('Error removing auth token: $e');
    }
  }

  Future<void> signOut() async {
    try {
      // Clear local token
      await removeAuthToken();

      // Clear local session
      await removeSessionId();

      // Clear any other stored data
      localStorage.clear();

      // go to login screen
      Navigator.pushReplacementNamed(context, '/login');

      final prefs = await SharedPreferences.getInstance();
      await prefs.clear();
    } catch (e) {
      print('Error during sign out: $e');
      throw Exception('Failed to sign out');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
          tooltip: 'Back to Home',
        ),
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Theme.of(context).colorScheme.primary.withOpacity(0.05),
              Theme.of(context).colorScheme.surface,
            ],
          ),
        ),
        child: Center(
          child: SingleChildScrollView(
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _buildHeader(context),
                  const SizedBox(height: 48),
                  _buildLoginCard(context),
                  const SizedBox(height: 24),
                  _buildFooter(context),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Column(
      children: [
        MouseRegion(
          cursor: SystemMouseCursors.click,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeInOut,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Theme.of(context).colorScheme.primary.withOpacity(0.1),
            ),
            child: Image.asset(
              'assets/images/logo.png',
              width: 64,
              height: 64,
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text(
          'ScrollWise AI',
          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                color: Theme.of(context).colorScheme.primary,
                fontWeight: FontWeight.bold,
              ),
        ),
      ],
    );
  }

  Widget _buildLoginCard(BuildContext context) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
        side: BorderSide(
          color: Theme.of(context).colorScheme.outline.withOpacity(0.2),
        ),
      ),
      child: Container(
        padding: const EdgeInsets.all(32.0),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(24),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Theme.of(context).cardColor,
              Theme.of(context).cardColor.withOpacity(0.8),
            ],
          ),
        ),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Welcome Back',
                style: Theme.of(context).textTheme.headlineSmall,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                'Sign in to continue to ScrollWise',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context)
                          .colorScheme
                          .onSurface
                          .withOpacity(0.6),
                    ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              _buildEmailField(),
              const SizedBox(height: 16),
              _buildPasswordField(),
              const SizedBox(height: 24),
              _buildLoginButton(),
              const SizedBox(height: 16),
              _buildRegisterButton(),
              if (_isLoading) ...[
                const SizedBox(height: 24),
                const LinearProgressIndicator(),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmailField() {
    return TextFormField(
      controller: _emailController,
      decoration: InputDecoration(
        labelText: 'Email',
        hintText: 'Enter your email',
        prefixIcon: const Icon(Icons.email_outlined),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(
            color: Theme.of(context).colorScheme.outline,
          ),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(
            color: Theme.of(context).colorScheme.outline.withOpacity(0.3),
          ),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(
            color: Theme.of(context).colorScheme.primary,
            width: 2,
          ),
        ),
        filled: true,
        fillColor: Theme.of(context).colorScheme.surface,
      ),
      keyboardType: TextInputType.emailAddress,
      textInputAction: TextInputAction.next,
      validator: (value) {
        if (value == null || value.isEmpty) {
          return 'Please enter your email';
        }
        if (!value.contains('@')) {
          return 'Please enter a valid email';
        }
        return null;
      },
    );
  }

  Widget _buildPasswordField() {
    return TextFormField(
      controller: _passwordController,
      decoration: InputDecoration(
        labelText: 'Password',
        hintText: 'Enter your password',
        prefixIcon: const Icon(Icons.lock_outline),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      obscureText: true,
      textInputAction: TextInputAction.done,
      onFieldSubmitted: (_) => _handleSubmit(),
      validator: (value) {
        if (value == null || value.isEmpty) {
          return 'Please enter your password';
        }
        if (value.length < 6) {
          return 'Password must be at least 6 characters';
        }
        return null;
      },
    );
  }

  Widget _buildLoginButton() {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      child: FilledButton.icon(
        onPressed: _isLoading ? null : _handleSubmit,
        icon: _isLoading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              )
            : const Icon(Icons.login),
        label: Text(_isLoading ? 'Signing In...' : 'Sign In'),
        style: FilledButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 20),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
    );
  }

  Widget _buildRegisterButton() {
    return OutlinedButton.icon(
      onPressed: _isLoading ? null : _handleRegister,
      icon: const Icon(Icons.person_add_outlined),
      label: const Text('Create Account'),
      style: OutlinedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 20),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
    );
  }

  Widget _buildFooter(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _buildFooterButton(
          icon: Icons.help_outline,
          label: 'Need Help?',
          onPressed: () {
            // Add help functionality
          },
        ),
        const SizedBox(width: 24),
        _buildFooterButton(
          icon: Icons.privacy_tip_outlined,
          label: 'Privacy Policy',
          onPressed: () {
            showDialog(
              context: context,
              builder: (BuildContext context) => const PrivacyPolicyDialog(),
            );
          },
        ),
      ],
    );
  }

  Widget _buildFooterButton({
    required IconData icon,
    required String label,
    required VoidCallback onPressed,
  }) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: TextButton.icon(
        onPressed: onPressed,
        icon: Icon(icon, size: 18),
        label: Text(label),
        style: TextButton.styleFrom(
          padding: const EdgeInsets.symmetric(
            horizontal: 16,
            vertical: 12,
          ),
        ),
      ),
    );
  }
}
