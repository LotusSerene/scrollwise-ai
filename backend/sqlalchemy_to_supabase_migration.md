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
| `delete_location`                              | []     |                                                                         |
| `delete_event`                                 | []     |                                                                         |
| `mark_chapter_processed`                        | []     |                                                                         |
| `is_chapter_processed_for_type`                | []     |                                                                         |
| `get_event_by_id`                              | []     |                                                                         |
| `get_location_by_id`                           | []     |                                                                         |
| `update_codex_item_embedding_id`               | []     |                                                                         |
| `create_project`                               | []     |                                                                         |
| `get_projects_by_universe`                     | []     |                                                                         |
| `get_project`                                  | [x]     | Converted to Supabase query                                             |
| `update_project`                               | []     |                                                                         |
| `update_project_universe`                      | []     |                                                                         |
| `delete_project`                               | []     |                                                                         |
| `create_universe`                              | []     |                                                                         |
| `get_universe`                                 | []     |                                                                         |
| `update_universe`                              | []     |                                                                         |
| `delete_universe`                              | []     |                                                                         |
| `get_universe_codex`                           | []     |                                                                         |
| `get_universe_knowledge_base`                  | []     |                                                                         |
| `get_characters`                               | []     |                                                                         |
| `get_events`                                   | []     |                                                                         |
| `get_locations`                                | []     |                                                                         |
| `mark_latest_chapter_processed`                | []     |                                                                         |
| `is_chapter_processed`                         | []     |                                                                         |
| `get_model_settings`                           | []     |                                                                         |
| `save_validity_check`                          | []     |                                                                         |
| `get_validity_check`                           | []     |                                                                         |
| `save_chat_history`                            | []     |                                                                         |
| `get_chat_history`                             | []     |                                                                         |
| `delete_chat_history`                          | []     |                                                                         |
| `create_preset`                                | []     |                                                                         |
| `get_presets`                                  | []     |                                                                         |
| `delete_preset`                                | []     |                                                                         |
| `get_preset_by_name`                           | []     |                                                                         |
| `update_chapter_embedding_id`                  | []     |                                                                         |
| `delete_character_relationship`                | []     |                                                                         |
| `save_relationship_analysis`                   | []     |                                                                         |
| `get_character_relationships`                  | []     |                                                                         |
| `update_character_backstory`                   | []     |                                                                         |
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
