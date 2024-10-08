import React, { useState } from 'react';
import axios from 'axios';
import './Create.css';
import { getAuthToken } from '../utils/auth';
import { v4 as uuidv4 } from 'uuid';

function Create({ onChapterGenerated, previousChapters }) {
  const [chapterNumber, setChapterNumber] = useState(1);
  const [plot, setPlot] = useState('');
  const [writingStyle, setWritingStyle] = useState('');
  const [instructions, setInstructions] = useState('');
  const [styleGuide, setStyleGuide] = useState('');
  const [minWordCount, setMinWordCount] = useState(1000);
  const [characters, setCharacters] = useState({});
  const [chapterTitle, setChapterTitle] = useState('');
  const [chapterContent, setChapterContent] = useState('');
  const [error, setError] = useState(null);

  const handleGenerateChapter = async () => {
    const token = getAuthToken();
    const data = {
      numChapters: 1,
      plot,
      writingStyle,
      instructions,
      styleGuide,
      minWordCount,
      characters: JSON.stringify(characters),
      chapterTitle,
      previousChapters: JSON.stringify(previousChapters)
    };

    try {
      const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/generate`, data, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.data.chapters && response.data.chapters.length > 0) {
        const newChapter = response.data.chapters[0];
        setChapterContent(newChapter.chapter);
        setChapterTitle(newChapter.title);
        onChapterGenerated(newChapter);
      } else {
        setError('No chapter generated. Please try again.');
      }
    } catch (error) {
      console.error('Error generating chapter:', error);
      setError('Error generating chapter. Please try again later.');
    }
  };

  const handleSaveChapter = async () => {
    if (!chapterTitle || !chapterContent) {
      setError('Chapter title and content are required.');
      return;
    }

    const token = getAuthToken();
    const chapterId = uuidv4();

    try {
      await axios.post(`${process.env.REACT_APP_API_URL}/api/chapters`, {
        name: `Chapter ${chapterNumber}`,
        content: chapterContent,
        title: chapterTitle
      }, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      setError(null);
      setChapterNumber(chapterNumber + 1);
      setChapterContent('');
      setChapterTitle('');
    } catch (error) {
      console.error('Error saving chapter:', error);
      setError('Error saving chapter. Please try again later.');
    }
  };

  return (
    <div className="create-container">
      <div className="input-section">
        <h3>Create New Chapter</h3>
        {error && <p className="error">{error}</p>}
        <label>
          Chapter Number:
          <input
            type="number"
            value={chapterNumber}
            onChange={(e) => setChapterNumber(e.target.value)}
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
          Characters:
          <textarea
            value={JSON.stringify(characters, null, 2)}
            onChange={(e) => setCharacters(JSON.parse(e.target.value))}
            rows={5}
            cols={40}
          />
        </label>
        <label>
          Chapter Title:
          <input
            type="text"
            value={chapterTitle}
            onChange={(e) => setChapterTitle(e.target.value)}
          />
        </label>
        <button onClick={handleGenerateChapter}>Generate Chapter</button>
        <button onClick={handleSaveChapter}>Save Chapter</button>
      </div>
      <div className="generated-chapter">
        <h3>Generated Chapter</h3>
        <pre>{chapterContent}</pre>
      </div>
    </div>
  );
}

export default Create;
