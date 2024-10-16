import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';
// Import DashboardScreen

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
          Uri.parse('$apiUrl/auth/token'),
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          body: {
            'username': _emailController.text,
            'password': _passwordController.text,
          },
        );

        if (response.statusCode == 200) {
          final data = json.decode(response.body);
          if (data['access_token'] != null) {
            widget.onLogin(data['access_token']);
            await setAuthToken(data['access_token']); // Store the token
            Fluttertoast.showToast(msg: 'Login successful!');
            Navigator.pushReplacementNamed(context, '/dashboard');
          } else {
            Fluttertoast.showToast(msg: 'Invalid credentials');
          }
        } else {
          Fluttertoast.showToast(msg: 'Error logging in');
        }
      } catch (error) {
        print('Login error: $error');
        Fluttertoast.showToast(msg: 'Error logging in');
      } finally {
        setState(() {
          _isLoading = false;
        });
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
            'username': _emailController.text,
            'password': _passwordController.text,
          }),
        );

        if (response.statusCode == 201) {
          Fluttertoast.showToast(
              msg: 'Registration successful! Please log in.');
        } else {
          Fluttertoast.showToast(msg: 'Error registering');
        }
      } catch (error) {
        print('Registration error: $error');
        Fluttertoast.showToast(msg: 'Error registering');
      } finally {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Login')),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Card(
          elevation: 8,
          child: Padding(
            padding: const EdgeInsets.all(20.0),
            child: Form(
              key: _formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextFormField(
                    controller: _emailController,
                    decoration: const InputDecoration(labelText: 'Email'),
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter your email';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 20),
                  TextFormField(
                    controller: _passwordController,
                    decoration: const InputDecoration(labelText: 'Password'),
                    obscureText: true,
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter your password';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 30),
                  ElevatedButton(
                    onPressed: _isLoading ? null : _handleSubmit,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 50, vertical: 15),
                    ),
                    child: _isLoading
                        ? const CircularProgressIndicator(
                            valueColor:
                                AlwaysStoppedAnimation<Color>(Colors.white),
                          )
                        : const Text('Login', style: TextStyle(fontSize: 18)),
                  ),
                  const SizedBox(height: 10),
                  ElevatedButton(
                    onPressed: _isLoading ? null : _handleRegister,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 50, vertical: 15),
                    ),
                    child: _isLoading
                        ? const CircularProgressIndicator(
                            valueColor:
                                AlwaysStoppedAnimation<Color>(Colors.white),
                          )
                        : const Text('Register',
                            style: TextStyle(fontSize: 18)),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
