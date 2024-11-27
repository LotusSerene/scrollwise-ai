# Features

## High Priority

## Medium Priority

TODO: Add a landing page, white listing for beta testing, and better login functionallity. (Landing page done)

TODO: Add a feature that allows users to collaborate with others on the story, such as sharing the knowledge base with others or allowing them to edit it. This can be done by making it so that every user can have for every project some sort of token that can be sent to other users to allow them to edit the project. With this token, the user can access the project's knowledge base and make changes to it. The changes will be saved to the project's knowledge base and will be visible to all users who have access to the project.

## Low Priority

TODO: Maybe add a feature called "Architect", That allows users to use another AI Model that influences the output of the main AI.

TODO: We can introduce Acts, Stages and maybe Sub-Stages, that can help the user to structure their story better. using acts, stages and/or substages we can have something like this

Act 1: <Example>
  Stage 1: <Something happens here>
  Stage 2: <We advance to here>

Act 2: So on and so forth



TODO: Making Editor better with functions, and AI-Powered Writing Assistance or AI Autocomplete.

TODO: Each project can have a story outline, and story plot, even though in create tab we have a way of adding Plots and Story Outlines, we should make it so that each project has its own story outline and story plot.

# Improvements

TODO: Connect Supabase to login

# Bugs

I'm not sure if we are using the correct terminology for the things we are trying to do, we should make sure we are using the correct terminology so that we can avoid any confusion.

# Ideas

## Run Commands
source .venv/Scripts/activate
cd backend/; uvicorn server:app --host 0.0.0.0 --port 8080 --reload
cd frontend/; flutter run -d chrome
chroma run --path ./chroma_data --host 0.0.0.0 --port 8000

# Done

TODO: Change dashboard to be a seamless nice populating dashboard that populates it with Populate the knowledge base with relevant information (e.g., chapter summaries, character descriptions, world-building details). using generate_with_retrieval (Done)
TODO: Add a search bar to the dashboard that allows users to search for specific information within the knowledge base. (Done)
TODO: Implement a feature that allows users to add new chapters to the story, updating the knowledge base accordingly. (Done)
TODO: Add a feature that allows users to create and manage characters, including adding new characters and editing existing ones. (Done)
TODO: Implement a feature that allows users to delete characters from the knowledge base. (Done)
TODO: Add a feature that allows users to view and edit the world-building details of the story, such as the history, culture, and geography. (Done)
TODO: Change the way we handle characters, worldbuilding, items, etc into a new section called Codex, this way we can have a better organization of the app. (Done)
TODO: Implement a feature that allows users to import a knowledge base from a file, such as a PDF or a Markdown file. (Done)
IDEA: We can make the landing page more visually appealing and user friendly (Done, flutter is nice)
IDEA: We can add a feature that allows users to create and manage projects, with CRUD ability, projects can be explained like a frontend of our current frontend, we can pass a project id in our backend, we change the way we log in, when we login we'd see the project dashboard instead of our normal homescreen, when you click on the project you'd see the homescreen we currently have but for that project, each project has it's own id, each project has it's own chat history, chapters, etc, 1 user can have multiple projects, and can switch between them easily. The only thing that wont be project specific is the settings tab (Done)
IDEA: We can add a feature that allows users to view and edit the project's settings, such as the project name, description, and API key, this way we can delete the input of adding an API key to create. (Done)
TODO: Having a better database (Done, PostegreSQL)
TODO: making sure this wepapp can be viewed gracefully on mobile phones (Flutter is nice, we have it just need to make sure it's working)
IDEA: Should we continue using react or switch to Flutter (We decided to switch to Flutter)

// BUG: When generating chapters we in Editor we see 2 of the same chapter, are we generating 2 chapters at one or are we saving it twice? (Fixed)
// BUG: We need to connect generate_title from Agent manager to the title of the chapter in the database so that we can generate titles for the chapters and save them to the database. (Fixed)
// BUG: When generating a chapter, we save characters even if we already have them in the database, we should fix this (Fixed)
// BUG: We Can view validity checks but there's no title to them, we have to connect each validity to it's chapter from the title. (Fixed)
// BUG: We need to make sure that the user is who they say they are when they are trying to access their projects, we can do this by adding an email verification step to the login process. (Fixed)
// BUG: we get Error generating chapters. Please try again later. when we try to generate a chapter, even though we did actually generate the chapter. (Fixed)

TODO: We should implement a changelog so that we can tell users what's changed in the app, this way they can see what's new and what's changed. (Done)

TODO: We should make it so that the user can see the progress of the chapter generation, this way they can see if the chapter is being generated or not and if it's taking longer than usual they can cancel it and try again. This can be done by adding a loading spinner or a progress bar to the page. This way the user can also see how long it's taking to generate the chapter and if it's taking longer than usual they can try again with different parameters or try again later. This can also prevent the user from clicking the generate button multiple times and generating multiple chapters at once, this can cause the page to crash and the user to lose all the data they entered. (Done)

TODO: Add Universes to the project, so that users can create multiple universes and switch between them. Universes can be shared through different projects, universes have shared knowledgebase, characters, lore, etc. (Done)

TODO: Add a tab that allows us to generate new Codex using the AI, this way we can generate new characters, items, locations, etc. This can be done by making it so that the user can select what they want to generate and then the AI will generate it for them. The AI will use the existing knowledge base to generate the new content. The new content will be added to the knowledge base and will be visible to the user. (done)

Bug: Chat history is not being saved or shown in the chat history. (Fixed)

Bug: Presets not loading (Fixed)

Bug: Preset throwing errors when successful. (Fixed)

TODO: Implement a feature that allows users to track the progress of the story, such as keeping track of the number of chapters written, the number of characters created, and the number of words written. And they can set the number of words or characters goal for the story. (Done)

TODO: Add a feature that allows users to view a timeline of the story, showing the order of events and the relationships between characters and chapters. (Done)

TODO: Implement a feature that allows users to view a map of the story's world, showing the locations of characters and events. (Done)

TODO: With Codex we now can add a feature that shows character journey, track their arc over time, show a relationship tree between characters, and show a timeline of events related to each character. (Done)

TODO: Add in Create we need to make it so the generate button disabled once 1 is clicked and enabled once the generation is done, this way we can prevent the user from clicking it multiple times and generating multiple chapters at once, this can cause the page to crash and the user to lose all the data they entered. (I think done?)

TODO: Make the styling of the page better, even my grandma can make something better than this (Done)

TODO: Making sure no other user can see anothers API KEY, this way we can prevent any unauthorized access to the API and any data breaches. This can be done by making sure the API KEY is stored in the database and is only accessible to the user who created it. This way we can also make sure that the API KEY is not visible to the user in the URL or in the console. (Done)

TODO: Ensuring server.py can handle multiple users at once, this way we can have multiple users using the app at the same time without any issues. (Done)

Todo: Make sure we add events, locations, backstories, etc to the knowledge base. (Done)

in Editor, Dashboard and project screen, we don't have consistent word count (Fixed)

BUG: Fix the event/location/etc not showing properly. (Fixed)

TODO: Ensuring server.py can handle multiple users at once, this way we can have multiple users using the app at the same time without any issues. (Done)

TODO: Add a feature that allows users to export the knowledge base in a format that can be easily shared with others, such as a PDF or a Markdown file. And to be able to import docs to the editor to be saved as chapters, you can import as many as you want, the title would be the docs filename and content being the content (Done)
