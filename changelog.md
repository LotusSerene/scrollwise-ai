# Changelog

## 0.0.1

- Implemented a dynamic dashboard that seamlessly populates with information retrieved from the knowledge base, including chapter summaries, character descriptions, and world-building details, utilizing the `generate_with_retrieval` function.

## 0.0.2

- Integrated a search bar into the dashboard, enabling users to efficiently locate specific information within the knowledge base.

## 0.0.3

- Added functionality for users to create new chapters and update the knowledge base accordingly, ensuring data consistency and facilitating story progression.

## 0.0.4

- Implemented a comprehensive character management system, allowing users to create, edit, and manage character profiles within the knowledge base.

## 0.0.5

- Enhanced character management by enabling users to delete characters from the knowledge base, providing greater control over story elements.

## 0.0.6

- Introduced a world-building feature, empowering users to view and edit details such as history, culture, and geography, enriching the story's context.

## 0.0.7

- Restructured the organization of characters, world-building elements, and items into a dedicated "Codex" section, improving the app's overall structure and navigation.

## 0.0.8

- Implemented knowledge base import functionality, allowing users to seamlessly integrate existing information from files such as PDFs and Markdown documents.

## 0.0.9

- Revamped the landing page with a focus on enhanced visual appeal and user-friendliness, creating a more welcoming and intuitive user experience.

## 0.0.10

- Introduced project management capabilities, enabling users to create, read, update, and delete projects. Each project functions as a separate instance of the application's frontend, utilizing a unique project ID for backend communication. User login now directs to a project dashboard, providing access to project-specific homescreens, chat histories, chapters, and other data. Settings remain global and are not project-specific.

## 0.0.11

- Integrated project settings functionality, allowing users to manage project-specific details such as name, description, and API key, eliminating the need for manual API key entry during project creation.

## 0.0.12

- Upgraded the database to PostgreSQL, improving data management, performance, and scalability.

## 0.0.13

- Optimized the web application for graceful rendering on mobile devices, ensuring a consistent and user-friendly experience across different platforms.

## 0.0.14

- Transitioned the frontend development framework from React to Flutter, leveraging Flutter's cross-platform capabilities and performance benefits.

## 0.0.15

- Resolved an issue where duplicate chapters were being generated or saved in the editor.

## 0.0.16

- Connected the `_generate_title` function from the Agent Manager to the chapter title in the database, ensuring accurate title generation and storage.

## 0.0.17

- Addressed a problem where characters were being saved redundantly, even if they already existed in the database.

## 0.0.18

- Added titles to validity checks, improving clarity and organization.

## 0.0.19

- Resolved an error that prevented chapter generation, even when the chapter was successfully generated.

## 0.0.20

- Addressed an issue where presets were throwing errors even when successfully loaded.

## 0.0.21

- Implemented a changelog to track changes and updates within the application, providing users with a clear overview of new features and improvements.

## 0.0.22

- Added a progress indicator for chapter generation, allowing users to monitor the generation process, cancel if necessary, and prevent accidental multiple chapter generation.

## 0.0.23

- Introduced the concept of universes, enabling users to create and manage multiple universes within the project, each with its own knowledge base, characters, and lore.

## 0.0.24

- Implemented AI-powered Codex generation, allowing users to generate new characters, items, and locations based on the existing knowledge base.

## 0.0.25

- Resolved an issue where chat history was not being saved or displayed correctly.

## 0.0.26

- Fixed a bug that prevented presets from loading properly.

## 0.0.27

- Implemented story progress tracking features, allowing users to monitor chapter count, character count, word count, and set goals for their stories.

## 0.0.28

- Added a story timeline feature that visualizes the order of events and relationships between characters and chapters.

## 0.0.29

- Integrated an interactive world map feature, enabling users to visualize and track locations of characters and events within the story's world.

## 0.0.30

- Enhanced the Codex system with character journey tracking, character arc visualization, relationships.

## 0.0.31

- Implemented safeguards in the Create section to prevent multiple simultaneous chapter generations by disabling the generate button during processing.

## 0.0.32

- Completely revamped the application's styling for improved visual appeal and user experience.

## 0.0.33

- Enhanced security by implementing proper API key storage and access controls, ensuring users can only access their own API keys.

## 0.0.34

- Optimized server.py to handle concurrent users efficiently, enabling smooth multi-user functionality.

## Recent Changes

### Refactor

- Migrated `update_codex_item` to use SQLAlchemy (38ee798)
- Migrated `delete_codex_item` to use SQLAlchemy (81b3c40)
- Migrated `get_codex_item_by_id` to use SQLAlchemy (1bb33c5)
- Use SQLAlchemy for API key storage (a3cf53c)
- Use SQLAlchemy to get and decrypt API key (ada1eaa)
- Remove API key using SQLAlchemy (ee0c581)
- Migrated `save_model_settings` to use SQLAlchemy (790f9b3)
- Update `create_location` to use SQLAlchemy (022e1b5)
- Migrated `delete_location` method to use SQLAlchemy (b5f12aa)

### Fixes

- Handle missing user in `save_api_key` (7766436)

## 0.0.40

- Migrated database from Remote to being local

## 1.0.2-beta

- Fix some issues I came across

## 1.0.3-beta

- Better logging and error handling
- Fixed presets not saving correctly
- Fixed Universes not creating correctly
- Remove approval check and waitlisting
- Update frontend to use scaffoldMessenger instead of AppNotification
- Better session management
- Fix uploading documents to knowledge base and editor
