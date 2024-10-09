import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Create.css';

const CreateChapter = ({ onChapterGenerated }) => {
  const [numChapters, setNumChapters] = useState(1);
  const [plot, setPlot] = useState('');
  const [writingStyle, setWritingStyle] = useState('');
  const [instructions, setInstructions] = useState('');
  const [styleGuide, setStyleGuide] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [generationModel, setGenerationModel] = useState('gemini-1.5-pro-002');
  const [checkModel, setCheckModel] = useState('gemini-1.5-pro-002');
  const [minWordCount, setMinWordCount] = useState(1000);
  const [characters, setCharacters] = useState([]);
  const [chapterContent, setChapterContent] = useState('');
  const [error, setError] = useState(null);
  const [previousChapters, setPreviousChapters] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false); // New state to track generation process

  useEffect(() => {
    const fetchPreviousChapters = async () => {
      try {
        const token = localStorage.getItem('token');
        const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/chapters`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setPreviousChapters(response.data.chapters);
      } catch (error) {
        console.error('Error fetching previous chapters:', error);
        setError('Error fetching previous chapters. Please try again later.');
      }
    };

    fetchPreviousChapters();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsGenerating(true); // Disable the button
    try {
      const token = localStorage.getItem('token');
      setError(null); // Clear any previous errors
      
      const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/generate`, {
        numChapters,
        plot,
        writingStyle,
        instructions: {
          styleGuide,
          minWordCount,
          additionalInstructions: instructions
        },
        characters: Object.fromEntries(characters.map(char => [char.name, char.description])),
        previousChapters,
        apiKey,
        generationModel,
        checkModel,
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.data.chapters && response.data.chapters.length > 0) {
        // Generate title for each chapter
        const chaptersWithTitles = response.data.chapters.map((chapter) => ({
          ...chapter,
          title: chapter.title
        }));

        if (onChapterGenerated) {
          onChapterGenerated(chaptersWithTitles);
        }
        setChapterContent(chaptersWithTitles.map(chapter => `${chapter.title}\n\n${chapter.content}`).join('\n\n'));
      } else {
        setError('No chapters were generated. Please try again.');
      }
    } catch (error) {
      console.error('Error generating chapters:', error);
      setError(error.response?.data?.message || 'Error generating chapters. Please try again later.');
    } finally {
      setIsGenerating(false); // Re-enable the button
    }
  };

  const handleAddCharacter = () => {
    const name = prompt("Enter character name:");
    const description = prompt("Enter character description:");
    if (name && description) {
      setCharacters((prevCharacters) => ({ ...prevCharacters, [name]: description }));
    }
  };

  const handleRemoveCharacter = (name) => {
    setCharacters((prevCharacters) => {
      const newCharacters = { ...prevCharacters };
      delete newCharacters[name];
      return newCharacters;
    });
  };

  return (
    <div className="create-container">
      <div className="input-section">
        <h3>Create New Chapter</h3>
        {error && <p className="error">{error}</p>}
        <label>
          Number of Chapters:
          <input
            type="number"
            value={numChapters}
            onChange={(e) => setNumChapters(e.target.value)}
            min={1}
          />
        </label>
        <label>
          Plot:
          <textarea
            value={plot}
            onChange={(e) => setPlot(e.target.value)}
            rows={5}
            cols={40}
          />
        </label>
        <label>
          Writing Style:
          <textarea
            value={writingStyle}
            onChange={(e) => setWritingStyle(e.target.value)}
            rows={3}
            cols={40}
          />
        </label>
        <label>
          Instructions:
          <textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            rows={3}
            cols={40}
          />
        </label>
        <label>
          Style Guide:
          <textarea
            value={styleGuide}
            onChange={(e) => setStyleGuide(e.target.value)}
            rows={3}
            cols={40}
          />
        </label>
        <label>
          Minimum Word Count:
          <input
            type="number"
            value={minWordCount}
            onChange={(e) => setMinWordCount(e.target.value)}
            min={0}
          />
        </label>
        <label>
          API Key:
          <input
            type="text"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </label>
        <label>
          Generation Model:
          <select value={generationModel} onChange={(e) => setGenerationModel(e.target.value)}>
            <option value="gemini-1.5-pro-002">Gemini 1.5 Pro</option>
            <option value="gemini-1.5-flash-002">Gemini 1.5 Flash</option>
            <option value="gemini-1.5-flash-8b">Gemini 1.5 Flash 8B</option>
          </select>
        </label>
        <label>
          Check Model:
          <select value={checkModel} onChange={(e) => setCheckModel(e.target.value)}>
            <option value="gemini-1.5-pro-002">Gemini 1.5 Pro</option>
            <option value="gemini-1.5-flash-002">Gemini 1.5 Flash</option>
            <option value="gemini-1.5-flash-8b">Gemini 1.5 Flash 8B</option>
          </select>
        </label>
        <label>
          Characters:
          <ul>
            {characters.map((char) => (
              <li key={char.name}>
                <strong>Name:</strong> {char.name}, <strong>Description:</strong> {char.description}
                <span className="remove-icon" onClick={() => handleRemoveCharacter(char.name)}>❌</span>
              </li>
            ))}
          </ul>
        </label>
        <button onClick={handleSubmit} disabled={isGenerating}>
          {isGenerating ? 'Generating...' : 'Generate Chapter'}
        </button>
      </div>
      <div className="generated-chapter">
        <h3>Generated Chapter</h3>
        <pre>{chapterContent}</pre>
      </div>
    </div>
  );
};

export default CreateChapter;
