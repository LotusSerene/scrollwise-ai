import 'package:flutter/material.dart';
import 'dart:math' as math;
import 'package:flutter/scheduler.dart';
import 'package:url_launcher/url_launcher.dart';

class LandingScreen extends StatelessWidget {
  const LandingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        elevation: 0,
        backgroundColor: Colors.transparent,
      ),
      body: AnimatedBackground(
        child: SingleChildScrollView(
          child: Column(
            children: [
              _buildWelcomeSection(context),
              _buildTutorialSection(context),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildWelcomeSection(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(48),
      child: Column(
        children: [
          Image.asset(
            'assets/images/logo.png',
            width: 120,
            height: 120,
          ),
          const SizedBox(height: 24),
          Text(
            'Welcome to ScrollWise',
            style: Theme.of(context).textTheme.displayMedium,
          ),
          const SizedBox(height: 16),
          Text(
            'Your AI-Powered Writing Studio',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 32),
          _buildFeaturesList(context),
          const SizedBox(height: 32),
          FilledButton.icon(
            onPressed: () => Navigator.pushReplacementNamed(
                context, '/projects'), // Navigate directly to projects
            icon: const Icon(Icons.rocket_launch_outlined), // Changed icon
            label: const Text('Go to Projects'), // Changed text
          ),
          const SizedBox(height: 16),
          Text(
            'Beta v1.0.6',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeaturesList(BuildContext context) {
    final features = [
      '🤖 AI-Powered Writing Assistance',
      '📚 Dynamic Story Dashboard',
      '🎭 Character Management & Journey Tracking',
      '🗺️ Interactive World Building',
      '📊 Story Progress Tracking',
      '📅 Timeline Visualization',
    ];

    return Wrap(
      alignment: WrapAlignment.center,
      spacing: 16,
      runSpacing: 8,
      children: features
          .map((feature) => Chip(
                label: Text(feature),
                backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                labelStyle: TextStyle(
                  color: Theme.of(context).colorScheme.onPrimaryContainer,
                ),
              ))
          .toList(),
    );
  }

  Widget _buildTutorialSection(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(48),
      child: Column(
        children: [
          Text(
            'Join Our Community',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton.filled(
                onPressed: () async {
                  final Uri url = Uri.parse('https://discord.gg/R8PUtxFPUq');
                  if (!await launchUrl(url)) {
                    throw Exception('Could not launch $url');
                  }
                },
                icon: const Icon(Icons.discord),
                iconSize: 32,
              ),
              const SizedBox(width: 16),
              IconButton.filled(
                onPressed: () async {
                  final Uri url =
                      Uri.parse('https://github.com/LotusSerene/scrollwise-ai');
                  if (!await launchUrl(url)) {
                    throw Exception('Could not launch $url');
                  }
                },
                icon: const Icon(Icons.developer_mode),
                iconSize: 32,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class AnimatedBackground extends StatefulWidget {
  final Widget child;
  const AnimatedBackground({Key? key, required this.child}) : super(key: key);

  @override
  State<AnimatedBackground> createState() => _AnimatedBackgroundState();
}

class _AnimatedBackgroundState extends State<AnimatedBackground>
    with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  final List<Bubble> _bubbles = [];
  final int _bubbleCount = 30;

  @override
  void initState() {
    super.initState();
    _initializeBubbles();
    _ticker = createTicker(_onTick)..start();
  }

  void _initializeBubbles() {
    final random = math.Random();
    for (int i = 0; i < _bubbleCount; i++) {
      _bubbles.add(Bubble(
        position: Offset(
          random.nextDouble(),
          random.nextDouble(),
        ),
        size: random.nextDouble() * 30 + 10,
        speed: random.nextDouble() * 0.001 + 0.001,
        color: HSLColor.fromAHSL(
          0.2,
          random.nextDouble() * 360,
          0.6,
          0.7,
        ).toColor(),
      ));
    }
  }

  void _onTick(Duration elapsed) {
    setState(() {
      for (var bubble in _bubbles) {
        bubble.position = Offset(
          bubble.position.dx,
          bubble.position.dy - bubble.speed,
        );

        if (bubble.position.dy < -0.1) {
          bubble.position = Offset(
            bubble.position.dx,
            1.1,
          );
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Theme.of(context).colorScheme.primary.withOpacity(0.1),
                Theme.of(context).colorScheme.secondary.withOpacity(0.1),
                Theme.of(context).colorScheme.surface,
              ],
            ),
          ),
        ),
        CustomPaint(
          painter: BubblePainter(
            bubbles: _bubbles,
            color: Theme.of(context).colorScheme.primary,
          ),
          size: Size.infinite,
        ),
        widget.child,
      ],
    );
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }
}

class Bubble {
  Offset position;
  final double size;
  final double speed;
  final Color color;

  Bubble({
    required this.position,
    required this.size,
    required this.speed,
    required this.color,
  });
}

class BubblePainter extends CustomPainter {
  final List<Bubble> bubbles;
  final Color color;

  const BubblePainter({
    required this.bubbles,
    required this.color,
  });

  @override
  void paint(Canvas canvas, Size size) {
    for (var bubble in bubbles) {
      final paint = Paint()
        ..color = bubble.color
        ..style = PaintingStyle.fill;

      canvas.drawCircle(
        Offset(
          bubble.position.dx * size.width,
          bubble.position.dy * size.height,
        ),
        bubble.size,
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant BubblePainter oldDelegate) => true;
}
