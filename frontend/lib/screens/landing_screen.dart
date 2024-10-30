import 'package:flutter/material.dart';

class LandingScreen extends StatelessWidget {
  const LandingScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        elevation: 0,
        backgroundColor: Colors.transparent,
        actions: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0),
            child: FilledButton(
              onPressed: () => Navigator.pushNamed(context, '/login'),
              child: const Text('Login'),
            ),
          ),
        ],
      ),
      body: SingleChildScrollView(
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
    );
  }

  Widget _buildHeroSection(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height * 0.8,
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Theme.of(context).colorScheme.primary.withOpacity(0.1),
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
            'ScrollWise AI',
            style: Theme.of(context).textTheme.displayLarge?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 16),
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
          FilledButton.icon(
            onPressed: () => Navigator.pushNamed(context, '/login'),
            icon: const Icon(Icons.edit),
            label: const Text('Start Writing'),
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(
                horizontal: 32,
                vertical: 20,
              ),
            ),
          ),
        ],
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
}
