import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:math' as math;
import 'package:flutter/scheduler.dart';

class LandingScreen extends StatelessWidget {
  const LandingScreen({Key? key}) : super(key: key);

  void _showContactForm(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => const ContactFormSheet(),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        elevation: 0,
        backgroundColor: Colors.transparent,
        actions: [
          TextButton(
            onPressed: () => _showContactForm(context),
            child: const Text('Contact Us'),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0),
            child: FilledButton(
              onPressed: () => Navigator.pushNamed(context, '/login'),
              child: const Text('Login'),
            ),
          ),
        ],
      ),
      body: AnimatedBackground(
        child: RawScrollbar(
          thumbColor: Theme.of(context).colorScheme.primary.withOpacity(0.3),
          radius: const Radius.circular(20),
          thickness: 8,
          thumbVisibility: true,
          child: ScrollConfiguration(
            behavior: ScrollConfiguration.of(context).copyWith(
              physics: const BouncingScrollPhysics(),
              scrollbars: false,
            ),
            child: SingleChildScrollView(
              child: Column(
                children: [
                  _buildHeroSection(context),
                  _buildFeaturesSection(context),
                  _buildUseCasesSection(context),
                  _buildAISection(context),
                  _buildCTASection(context),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeroSection(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height,
      padding: const EdgeInsets.symmetric(horizontal: 48, vertical: 64),
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
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Image.asset(
            'assets/images/logo.png',
            width: 120,
            height: 120,
          ),
          const SizedBox(height: 32),
          Text(
            'Transform Your Writing Process with AI',
            style: Theme.of(context).textTheme.displayLarge?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                  fontWeight: FontWeight.bold,
                  height: 1.2,
                ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          Text(
            'Your AI-Powered Writing Companion',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color:
                      Theme.of(context).colorScheme.onSurface.withOpacity(0.8),
                ),
          ),
          const SizedBox(height: 32),
          SizedBox(
            width: 600,
            child: Text(
              'Craft intricate stories, manage complex narratives, and bring your creative vision to life with the power of AI.',
              style: Theme.of(context).textTheme.bodyLarge,
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 48),
          _buildAnimatedCTAButton(context),
        ],
      ),
    );
  }

  Widget _buildAnimatedCTAButton(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        child: FilledButton.icon(
          onPressed: () => Navigator.pushNamed(context, '/login'),
          icon: const Icon(Icons.edit),
          label: const Text('Start Now!'),
          style: FilledButton.styleFrom(
            padding: const EdgeInsets.symmetric(
              horizontal: 48,
              vertical: 24,
            ),
            textStyle: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildFeaturesSection(BuildContext context) {
    final features = [
      {
        'icon': Icons.auto_stories,
        'title': 'Project Management',
        'description':
            'Organize your stories into projects and universes. Keep your writing organized and accessible.',
      },
      {
        'icon': Icons.psychology,
        'title': 'AI-Powered Writing',
        'description':
            'Generate chapters, develop characters, and expand your story with advanced AI assistance.',
      },
      {
        'icon': Icons.people,
        'title': 'Character Development',
        'description':
            'Track character relationships, journeys, and backstories with our comprehensive character management system.',
      },
      {
        'icon': Icons.timeline,
        'title': 'Timeline & Events',
        'description':
            'Visualize your story\'s timeline, manage events, and maintain narrative consistency.',
      },
      {
        'icon': Icons.book,
        'title': 'Codex System',
        'description':
            'Build and maintain a rich knowledge base of your story\'s world, characters, and lore.',
      },
      {
        'icon': Icons.check_circle,
        'title': 'Validity Checks',
        'description':
            'Ensure consistency and quality with automated story validation and suggestions.',
      },
    ];

    return Container(
      padding: const EdgeInsets.all(64),
      child: Column(
        children: [
          Text(
            'Features',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 48),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 3,
              crossAxisSpacing: 32,
              mainAxisSpacing: 32,
              childAspectRatio: 1.2,
            ),
            itemCount: features.length,
            itemBuilder: (context, index) {
              return _buildFeatureCard(
                context,
                features[index]['icon'] as IconData,
                features[index]['title'] as String,
                features[index]['description'] as String,
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildFeatureCard(
    BuildContext context,
    IconData icon,
    String title,
    String description,
  ) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        child: Card(
          elevation: 0,
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  icon,
                  size: 48,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(height: 16),
                Text(
                  title,
                  style: Theme.of(context).textTheme.titleLarge,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  description,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context)
                            .colorScheme
                            .onSurface
                            .withOpacity(0.7),
                      ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildUseCasesSection(BuildContext context) {
    final useCases = [
      {
        'image': 'assets/images/novelist.jpg',
        'title': 'Novelists',
        'description':
            'Perfect for writing and managing long-form fiction, character arcs, and complex plot lines.',
        'features': [
          'Chapter Generation',
          'Character Development',
          'Plot Consistency'
        ]
      },
      {
        'image': 'assets/images/worldbuilder.jpg',
        'title': 'World Builders',
        'description':
            'Create and manage vast fictional universes with interconnected lore, locations, and histories.',
        'features': [
          'Universe Management',
          'Location Tracking',
          'Cultural Development'
        ]
      },
      {
        'image': 'assets/images/screenwriter.jpg',
        'title': 'Screenwriters',
        'description':
            'Develop scripts with strong character relationships and coherent timelines.',
        'features': [
          'Scene Organization',
          'Character Relationships',
          'Event Timeline'
        ]
      },
    ];

    return Container(
      padding: const EdgeInsets.all(64),
      color: Theme.of(context).colorScheme.surface,
      child: Column(
        children: [
          Text(
            'Who It\'s For',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 48),
          ListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: useCases.length,
            itemBuilder: (context, index) {
              final useCase = useCases[index];
              return Padding(
                padding: const EdgeInsets.only(bottom: 48.0),
                child: _buildUseCaseCard(context, useCase),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildUseCaseCard(BuildContext context, Map<String, dynamic> useCase) {
    return Card(
      elevation: 0,
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: Image.asset(
                useCase['image'] as String,
                width: 300,
                height: 200,
                fit: BoxFit.cover,
              ),
            ),
            const SizedBox(width: 32),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    useCase['title'] as String,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    useCase['description'] as String,
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                  const SizedBox(height: 24),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children:
                        (useCase['features'] as List<String>).map((feature) {
                      return Chip(
                        label: Text(feature),
                        backgroundColor:
                            Theme.of(context).colorScheme.primaryContainer,
                      );
                    }).toList(),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAISection(BuildContext context) {
    final aiFeatures = [
      {
        'title': 'Smart Chapter Generation',
        'description':
            'Generate chapters that maintain consistency with your story\'s context and style.',
        'icon': Icons.auto_awesome,
      },
      {
        'title': 'Character Analysis',
        'description':
            'Automatically extract character relationships and development from your writing.',
        'icon': Icons.psychology_alt,
      },
      {
        'title': 'Intelligent Suggestions',
        'description':
            'Receive context-aware suggestions for plot development and world-building.',
        'icon': Icons.lightbulb,
      },
      {
        'title': 'Style Consistency',
        'description':
            'Maintain consistent writing style and tone throughout your story.',
        'icon': Icons.style,
      },
    ];

    return Container(
      padding: const EdgeInsets.all(64),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Theme.of(context).colorScheme.primaryContainer,
            Theme.of(context).colorScheme.surface,
          ],
        ),
      ),
      child: Column(
        children: [
          Text(
            'AI-Powered Writing Assistant',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 16),
          Text(
            'Harness the power of advanced AI to enhance your writing process',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color:
                      Theme.of(context).colorScheme.onSurface.withOpacity(0.7),
                ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 48),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 32,
              mainAxisSpacing: 32,
              childAspectRatio: 1.5,
            ),
            itemCount: aiFeatures.length,
            itemBuilder: (context, index) {
              return _buildAIFeatureCard(
                context,
                aiFeatures[index]['icon'] as IconData,
                aiFeatures[index]['title'] as String,
                aiFeatures[index]['description'] as String,
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildAIFeatureCard(
    BuildContext context,
    IconData icon,
    String title,
    String description,
  ) {
    return Card(
      elevation: 0,
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              size: 48,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 16),
            Text(
              title,
              style: Theme.of(context).textTheme.titleLarge,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              description,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context)
                        .colorScheme
                        .onSurface
                        .withOpacity(0.7),
                  ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCTASection(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 64, vertical: 96),
      child: Column(
        children: [
          Text(
            'Ready to Start Your Writing Journey?',
            style: Theme.of(context).textTheme.headlineMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: 600,
            child: Text(
              'Join ScrollWise AI today and transform your writing process with the power of artificial intelligence.',
              style: Theme.of(context).textTheme.bodyLarge,
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 48),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              FilledButton.icon(
                onPressed: () => Navigator.pushNamed(context, '/login'),
                icon: const Icon(Icons.edit),
                label: const Text('Start Writing Now'),
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 32,
                    vertical: 20,
                  ),
                ),
              ),
              const SizedBox(width: 16),
              OutlinedButton.icon(
                onPressed: () {
                  // Add link to documentation or demo
                },
                icon: const Icon(Icons.play_circle_outline),
                label: const Text('Watch Demo'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 32,
                    vertical: 20,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  int _getGridCrossAxisCount(BuildContext context) {
    double width = MediaQuery.of(context).size.width;
    if (width > 1200) return 3;
    if (width > 800) return 2;
    return 1;
  }
}

class ContactFormSheet extends StatefulWidget {
  const ContactFormSheet({Key? key}) : super(key: key);

  @override
  State<ContactFormSheet> createState() => _ContactFormSheetState();
}

class _ContactFormSheetState extends State<ContactFormSheet> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _messageController = TextEditingController();

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _messageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
        left: 24,
        right: 24,
        top: 24,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Contact Us',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
            const SizedBox(height: 24),
            Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  TextFormField(
                    controller: _nameController,
                    decoration: const InputDecoration(
                      labelText: 'Name',
                      border: OutlineInputBorder(),
                    ),
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter your name';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _emailController,
                    decoration: const InputDecoration(
                      labelText: 'Email',
                      border: OutlineInputBorder(),
                    ),
                    keyboardType: TextInputType.emailAddress,
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter your email';
                      }
                      if (!value.contains('@')) {
                        return 'Please enter a valid email';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _messageController,
                    decoration: const InputDecoration(
                      labelText: 'Message',
                      border: OutlineInputBorder(),
                      alignLabelWithHint: true,
                    ),
                    maxLines: 5,
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter your message';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: () {
                      if (_formKey.currentState!.validate()) {
                        // Show success message
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Message sent! (Placeholder)'),
                            behavior: SnackBarBehavior.floating,
                          ),
                        );
                        Navigator.pop(context);
                      }
                    },
                    child: const Padding(
                      padding: EdgeInsets.symmetric(vertical: 16),
                      child: Text('Send Message'),
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ],
        ),
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
  final List<FloatingWord> _words = [];
  Offset _mousePosition = Offset.zero;
  final double _mouseInfluenceRadius = 150.0;

  final List<String> _wordList = [
    'Story',
    'Create',
    'Write',
    'Imagine',
    'AI',
    'Novel',
    'Chapter',
    'Character',
    'Plot',
    'World',
    'Adventure',
    'Journey',
    'Creativity',
    'Inspire',
    'Design',
    'Develop',
    'Build',
    'Dream',
  ];

  @override
  void initState() {
    super.initState();
    _initializeWords();
    _ticker = createTicker(_onTick)..start();
  }

  void _initializeWords() {
    final random = math.Random();
    for (int i = 0; i < 20; i++) {
      _words.add(FloatingWord(
        word: _wordList[random.nextInt(_wordList.length)],
        position: Offset(
          random.nextDouble() * 1.2 - 0.1,
          random.nextDouble() * 1.2 - 0.1,
        ),
        velocity: Offset(
          (random.nextDouble() - 0.5) * 0.02,
          (random.nextDouble() - 0.5) * 0.02,
        ),
        opacity: random.nextDouble() * 0.3,
        size: random.nextDouble() * 16 + 16, // Random size between 16 and 32
        rotation: random.nextDouble() * math.pi * 2, // Random rotation
        rotationSpeed:
            (random.nextDouble() - 0.5) * 0.02, // Random rotation speed
      ));
    }
  }

  void _onTick(Duration elapsed) {
    setState(() {
      for (var word in _words) {
        // Basic movement
        word.position += word.velocity;

        // Rotate words
        word.rotation += word.rotationSpeed;

        // Mouse interaction
        final mouseOffset = Offset(
          _mousePosition.dx / context.size!.width,
          _mousePosition.dy / context.size!.height,
        );

        final distance = (word.position - mouseOffset).distance;
        if (distance < _mouseInfluenceRadius / context.size!.width) {
          final angle = (word.position - mouseOffset).direction;
          final repelForce = 0.001 / (distance + 0.1);
          word.velocity += Offset(
            math.cos(angle) * repelForce,
            math.sin(angle) * repelForce,
          );
        }

        // Apply drag
        word.velocity *= 0.99;

        // Bounce off edges with damping
        if (word.position.dx < -0.1 || word.position.dx > 1.1) {
          word.velocity = Offset(-word.velocity.dx * 0.8, word.velocity.dy);
          word.position = Offset(
            word.position.dx < -0.1 ? -0.1 : 1.1,
            word.position.dy,
          );
        }
        if (word.position.dy < -0.1 || word.position.dy > 1.1) {
          word.velocity = Offset(word.velocity.dx, -word.velocity.dy * 0.8);
          word.position = Offset(
            word.position.dx,
            word.position.dy < -0.1 ? -0.1 : 1.1,
          );
        }

        // Pulsate opacity
        word.opacity =
            (math.sin(elapsed.inMilliseconds / 1000 * 0.5 + word.hashCode) +
                    1) *
                0.15;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onHover: (event) {
        setState(() {
          _mousePosition = event.localPosition;
        });
      },
      child: Stack(
        children: [
          // Gradient background
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
                stops: const [0.0, 0.5, 1.0],
              ),
            ),
          ),
          // Parallax background words
          CustomPaint(
            painter: BackgroundPainter(
              words: _words,
              color: Theme.of(context).colorScheme.primary,
              mousePosition: _mousePosition,
            ),
            size: Size.infinite,
          ),
          // Main content with parallax effect
          ParallaxContent(child: widget.child),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }
}

class FloatingWord {
  String word;
  Offset position;
  Offset velocity;
  double opacity;
  double size;
  double rotation;
  double rotationSpeed;

  FloatingWord({
    required this.word,
    required this.position,
    required this.velocity,
    required this.opacity,
    required this.size,
    required this.rotation,
    required this.rotationSpeed,
  });
}

class BackgroundPainter extends CustomPainter {
  final List<FloatingWord> words;
  final Color color;
  final Offset mousePosition;

  const BackgroundPainter({
    required this.words,
    required this.color,
    required this.mousePosition,
  });

  @override
  void paint(Canvas canvas, Size size) {
    for (var word in words) {
      canvas.save();

      final position = Offset(
        word.position.dx * size.width,
        word.position.dy * size.height,
      );

      // Rotate around word center
      final textPainter = TextPainter(
        text: TextSpan(
          text: word.word,
          style: TextStyle(
            color: color.withOpacity(word.opacity),
            fontSize: word.size,
            fontWeight: FontWeight.bold,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();

      canvas.translate(position.dx, position.dy);
      canvas.rotate(word.rotation);
      canvas.translate(-textPainter.width / 2, -textPainter.height / 2);

      textPainter.paint(canvas, Offset.zero);

      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(covariant BackgroundPainter oldDelegate) => true;
}

// Add this new widget for parallax scrolling
class ParallaxContent extends StatefulWidget {
  final Widget child;

  const ParallaxContent({Key? key, required this.child}) : super(key: key);

  @override
  State<ParallaxContent> createState() => _ParallaxContentState();
}

class _ParallaxContentState extends State<ParallaxContent> {
  final _scrollController = ScrollController();
  double _scroll = 0;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  void _onScroll() {
    setState(() {
      _scroll = _scrollController.offset;
    });
  }

  @override
  Widget build(BuildContext context) {
    return RawScrollbar(
      thumbColor: Theme.of(context).colorScheme.primary.withOpacity(0.3),
      radius: const Radius.circular(20),
      thickness: 8,
      thumbVisibility: true,
      controller: _scrollController,
      child: SingleChildScrollView(
        controller: _scrollController,
        child: Transform.translate(
          offset: Offset(0, _scroll * 0.1), // Parallax effect
          child: widget.child,
        ),
      ),
    );
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }
}
