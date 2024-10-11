// frontend/src/components/Create.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Create.css';
import { getAuthHeaders } from '../utils/auth';

const CreateChapter = ({ onChapterGenerated }) => {
  const [numChapters, setNumChapters] = useState(1);
  const [plot, setPlot] = useState('');
  const [writingStyle, setWritingStyle] = useState('');
  const [instructions, setInstructions] = useState('');
  const [styleGuide, setStyleGuide] = useState('');
  const [minWordCount, setMinWordCount] = useState(1000);
  const [chapterContent, setChapterContent] = useState('');
  const [error, setError] = useState(null);
  const [previousChapters, setPreviousChapters] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    const fetchPreviousChapters = async () => {
      try {
        const headers = getAuthHeaders();
        const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/chapters`, {
          headers: headers
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
    setIsGenerating(true);
    try {
      const headers = getAuthHeaders();
      setError(null);
      
      const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/generate`, {
        numChapters,
        plot,
        writingStyle,
        instructions: {
          styleGuide,
          minWordCount,
          additionalInstructions: instructions
        },
        previousChapters
      }, {
        headers: headers
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
      setIsGenerating(false);
    }
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
