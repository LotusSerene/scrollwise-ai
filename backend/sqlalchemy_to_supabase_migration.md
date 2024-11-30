# SQLAlchemy to Supabase Migration

| Method Name                                      | Status | Notes                                                                 |
|-------------------------------------------------|--------|-------------------------------------------------------------------------|
| `get_projects`                                  | [x]     | Converted to Supabase query                                             |
| `get_universes`                                | [x]     | Converted to Supabase query                                             |
| `check_user_approval`                           | [x]     | Converted to Supabase query                                             |
| `create_user`                                   | [x]     | Converted to Supabase auth API                                         |
| `get_user_by_email`                             | [x]     | Converted to Supabase query                                             |
| `get_all_chapters`                              | [x]    | Converted to Supabase query                                             |
| `create_chapter`                                | [x]     | Converted to Supabase query                                             |
| `update_chapter`                                | [x]     | Converted to Supabase query                                             |
| `delete_chapter`                                | [x]     | Converted to Supabase query                                             |
| `get_chapter`                                   | [x]    | Converted to Supabase query                                             |
| `get_all_validity_checks`                      | [x]     | Converted to Supabase query                                             |
| `delete_validity_check`                        | [x]     | Converted to Supabase query                                             |
| `create_codex_item`                             | [x]     | Converted to Supabase query                                             |
| `get_all_codex_items`                           | [x]     | Converted to Supabase query                                             |
| `update_codex_item`                             | [x]     | Converted to Supabase query                                             |
| `delete_codex_item`                             | [x]     | Converted to Supabase query                                             |
| `get_codex_item_by_id`                          | [x]     | Converted to Supabase query                                             |
| `save_api_key`                                 | [x]     | Converted to Supabase upsert                                             |
| `get_api_key`                                  | [x]     | Converted to Supabase query                                             |
| `remove_api_key`                               | [x]     | Converted to Supabase query                                             |
| `save_model_settings`                           | [x]     | Converted to Supabase query                                             |
| `create_location`                              | [x]     | Converted to Supabase query                                             |
| `delete_location`                              | [x]    | Converted to Supabase query                                             |
| `delete_event`                                 | [x]    | Converted to Supabase query                                             |
| `mark_chapter_processed`                        | [x]     | Converted to Supabase query                                             |
| `is_chapter_processed_for_type`                | [x]     | Converted to Supabase query                                             |
| `get_event_by_id`                              | [x]    | Converted to Supabase query                                             |
| `get_location_by_id`                           | [x]    | Converted to Supabasequery                                                                  |
| `update_codex_item_embedding_id`               | [x]    | Converted to Supabase query                                             |
| `create_project`                               | [x]    | Converted to Supabase query                                             |
| `get_projects_by_universe`                     | [x]    | Converted to Supabase query                                             |
| `get_project`                                  | [x]     | Converted to Supabase query                                             |
| `update_project`                               | [x]    | Converted to Supabase query                                             |
| `update_project_universe`                      | [x]     | Converted to Supabase query                                                                            |
| `delete_project`                               | [x]     | Converted to Supabase query                                             |
| `create_universe`                              | [x]     | Converted to Supabase query                                             |
| `get_universe`                                 | [x]    | Converted to Supabase query                                             |
| `update_universe`                              | [x]    | Converted to Supabase query                                             |
| `delete_universe`                              | [x]     | Converted to Supabase query                                             |
| `get_universe_codex`                           | [x]    | Converted to Supabase query                                             |
| `get_universe_knowledge_base`                  | [x]    | Converted to Supabase query                                             |
| `get_characters`                               | [x]    | Converted to Supabase query                                             |
| `get_events`                                   | [x]    | Converted to Supabase query                                             |
| `get_locations`                                | [x]    | Converted to Supabase query                                             |
| `mark_latest_chapter_processed`                | [x]     |  Converted to supabase query                                                                       |
| `is_chapter_processed`                         | [x]    | Converted to Supabase query                                             |
| `get_model_settings`                           | [x]    | Converted to Supabase query                                             |
| `save_validity_check`                          | [x]     |  Converted to Supabase query                                                                         |
| `get_validity_check`                           | [x]     |     Converted to Supabase query                                                                      |
| `save_chat_history`                            | [x]     |       Converted to Supabase query                                                                    |
| `get_chat_history`                             | [x]     | Converted to Supabase query                                                                          |
| `delete_chat_history`                          | [x]     |   Converted to Supabase query                                                                        |
| `create_preset`                                | [x]     |  Converted to Supabase query                                                                         |
| `get_presets`                                  | [x]     |      Converted to Supabase query                                                                     |
| `delete_preset`                                | [x]     |  Converted to Supabase query                                                                         |
| `get_preset_by_name`                           | [x]     |   Converted to Supabase query                                                                        |
| `update_chapter_embedding_id`                  | [x]     | Converted to Supabase query                                                                         |
| `delete_character_relationship`                | [x]     | Converted to Supabase query                                                                         |
| `save_relationship_analysis`                   | [x]     | Converted to Supabase query                                                                         |
| `get_character_relationships`                  | [x]     |  Converted to Supabase query                                                                        |
| `update_character_backstory`                   | [x]    | Converted to Supabase query                                             |
| `delete_character_backstory`                   | []     |                                                                         |
| `get_chapter_count`                            | []     |                                                                         |
| `create_event`                                 | []     |                                                                         |
| `save_character_backstory`                     | []     |                                                                         |
| `get_character_backstories`                    | []     |                                                                         |
| `get_latest_unprocessed_chapter_content`       | []     |                                                                         |
| `create_character_relationship`                | []     |                                                                         |
| `update_event`                                 | []     |                                                                         |
| `get_event_by_title`                           | []     |                                                                         |
| `update_location`                              | []     |                                                                         |
| `update_character_relationship`                | []     |                                                                         |
| `get_location_by_name`                         | []     |                                                                         |
| `create_location_connection`                   | []     |                                                                         |
| `create_event_connection`                      | []     |                                                                         |
| `get_location_connections`                     | []     |                                                                         |
| `get_event_connections`                        | []     |                                                                         |
| `update_location_connection`                   | []     |                                                                         |
| `update_event_connection`                      | []     |                                                                         |
| `delete_location_connection`                   | []     |                                                                         |
| `delete_event_connection`                      | []     |                                                                         |
| `approve_user`                                 | []     |                                                                         |
