import 'package:flutter/material.dart';
import 'package:jwt_decoder/jwt_decoder.dart';
import '../utils/auth.dart';
import '../widgets/privacy_policy_dialog.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:logging/logging.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:url_launcher/url_launcher.dart';

final _logger = Logger('Login');

class LoginScreen extends StatefulWidget {
  final Function(String) onLogin;

  const LoginScreen({Key? key, required this.onLogin}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
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
        final response = await Supabase.instance.client.auth.signInWithPassword(
          email: _emailController.text,
          password: _passwordController.text,
        );

        if (response.session != null) {
          // Get session ID from backend using the correct endpoint and format
          final serverResponse = await http.post(
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

          if (serverResponse.statusCode == 200) {
            final data = json.decode(serverResponse.body);
            final sessionId = data['session_id'];

            // Store the session ID
            await setSessionId(sessionId);

            // Call onLogin callback with Supabase token
            widget.onLogin(response.session!.accessToken);

            if (mounted) {
              Navigator.pushReplacementNamed(context, '/projects');
            }
          } else {
            throw Exception('Failed to get session ID from server');
          }
        }
      } on AuthException catch (error) {
        _logger.severe('Login error: $error');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: ${error.message}')),
          );
        }
      } catch (error) {
        _logger.severe('Login error: $error');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: ${error.toString()}')),
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
        // First sign up with Supabase
        final response = await Supabase.instance.client.auth.signUp(
          email: _emailController.text,
          password: _passwordController.text,
        );

        if (response.user != null) {
          // Then register with our backend
          final serverResponse = await http.post(
            Uri.parse('$apiUrl/auth/signup'),
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
            },
            body: json.encode({
              'email': _emailController.text,
              'password': _passwordController.text,
              'supabase_id': response.user!.id, // Pass the Supabase user ID
            }),
          );

          if (serverResponse.statusCode == 201) {
            if (mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Registration successful!'),
                ),
              );
              _emailController.clear();
              _passwordController.clear();
            }
          } else {
            throw Exception('Failed to register with backend');
          }
        }
      } on AuthException catch (error) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(error.message)),
          );
        }
      } catch (error) {
        _logger.severe('Registration error: $error');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(error.toString())),
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

  Future<bool> verifyAuthState() async {
    try {
      final token = await getAuthToken();
      final sessionId = await getSessionId();

      _logger.info('Verifying authentication state');

      if (token == null || sessionId == null) {
        _logger.warning('Missing token or sessionId');
        return false;
      }

      // Verify token is not expired
      try {
        if (JwtDecoder.isExpired(token)) {
          _logger.warning('Token is expired');
          return false;
        }

        _logger.info('Auth state verified successfully');
        return true;
      } catch (e) {
        _logger.severe('Error decoding/verifying token: $e');
        return false;
      }
    } catch (e) {
      _logger.severe('Error verifying auth state: $e');
      return false;
    }
  }

  Future<void> initializeSession(String accessToken, String sessionId) async {
    try {
      _logger.info('Initializing session with token and sessionId');

      // Store session ID first
      await setSessionId(sessionId);

      // Don't try to initialize Supabase session directly
      // Just store the access token locally
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('access_token', accessToken);

      // Verify storage
      final storedToken = await getAuthToken();
      final storedSessionId = await getSessionId();

      _logger.info('Session initialized successfully');

      if (storedToken == null || storedSessionId == null) {
        throw Exception('Failed to store session credentials');
      }
    } catch (e) {
      _logger.severe('Error initializing session: $e');
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
      _logger.severe('Error checking backend session: $e');
      return false;
    }
  }

  Future<String?> getAuthToken() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getString('access_token');
    } catch (e) {
      _logger.severe('Error getting auth token: $e');
      return null;
    }
  }

  Future<void> removeAuthToken() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('access_token');
    } catch (e) {
      _logger.severe('Error removing auth token: $e');
    }
  }

  Future<void> signOut() async {
    try {
      // Clear local token
      await removeAuthToken();

      // Clear local session
      await removeSessionId();

      final prefs = await SharedPreferences.getInstance();
      await prefs.clear();

      // Add mounted check before using context
      if (mounted) {
        Navigator.pushReplacementNamed(context, '/login');
      }
    } catch (e) {
      _logger.severe('Error during sign out: $e');
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
            showDialog(
              context: context,
              builder: (BuildContext context) => AlertDialog(
                title: const Text('Need Help?'),
                content: const Text(
                  'Join our Discord server or post an issue on GitHub for assistance.',
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Close'),
                  ),
                  TextButton(
                    onPressed: () async {
                      final Uri url = Uri.parse('https://discord.gg/QHkAMkss');
                      if (!await launchUrl(url)) {
                        throw Exception('Could not launch $url');
                      }
                    },
                    child: const Text('Join Discord'),
                  ),
                  TextButton(
                    onPressed: () async {
                      final Uri url = Uri.parse(
                          'https://github.com/LotusSerene/scrollwise-ai');
                      if (!await launchUrl(url)) {
                        throw Exception('Could not launch $url');
                      }
                    },
                    child: const Text('GitHub Issues'),
                  ),
                ],
              ),
            );
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
