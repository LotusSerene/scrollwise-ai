// frontend/src/components/Create.js
import React, { useState } from 'react';
import { getAuthHeaders } from '../utils/auth';
import { toast } from 'react-toastify';
import './Create.css'; // We'll create this file for styling

const CreateChapter = ({ onChapterGenerated }) => {
  const [numChapters, setNumChapters] = useState(1);
  const [plot, setPlot] = useState('');
  const [writingStyle, setWritingStyle] = useState('');
  const [styleGuide, setStyleGuide] = useState('');
  const [minWordCount, setMinWordCount] = useState(1000);
  const [additionalInstructions, setAdditionalInstructions] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [streamedContent, setStreamedContent] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsGenerating(true);
    setStreamedContent('');

    try {
      const headers = {
        ...getAuthHeaders(),
        'Content-Type': 'application/json',
      };

      const requestBody = {
        numChapters,
        plot,
        writingStyle,
        styleGuide,
        minWordCount,
        additionalInstructions,
        instructions: {
          styleGuide,
          minWordCount,
          additionalInstructions
        }
      };

      const response = await fetch(`${process.env.REACT_APP_API_URL}/chapters/generate`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(requestBody),
      });

      if (!response.body) {
        throw new Error("ReadableStream not supported in this browser.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        const chunkValue = decoder.decode(value);

        const lines = chunkValue.split('\n').filter(line => line.trim() !== '');

        for (const line of lines) {
          try {
            const data = JSON.parse(line);
            if (data.type === 'chunk') {
              setStreamedContent(prev => prev + data.content);
            } else if (data.type === 'final') {
              if (onChapterGenerated) {
                onChapterGenerated([{
                  id: data.chapterId,
                  title: data.title,
                  content: data.content,
                  validity: data.validity,
                  newCharacters: data.newCharacters
                }]);
              }
              toast.success('Chapter generated successfully');
            } else if (data.type === 'done') {
              console.log('All chapters generated');
              toast.success('All chapters generated successfully');
              setIsGenerating(false);
              // Optionally, you can trigger any final actions here
              break; // Exit the for loop as we're done
            } else if (data.error) {
              toast.error(`Error: ${data.error}`);
              setIsGenerating(false);
            }
          } catch (err) {
            console.error("Error parsing chunk:", err);
          }
        }
        
        if (done) break; // Exit the while loop if we're done reading
      }
    } catch (error) {
      console.error('Error generating chapters:', error);
      toast.error('Error generating chapters');
      setIsGenerating(false);
    }
  };

  return (
    <div className="create-container">
      <h2>Generate New Chapter</h2>
      <p className="instructions">
        Fill in the form below to generate a new chapter for your story. Provide as much detail as possible to get the best results.
      </p>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="numChapters">Number of Chapters:</label>
          <input
            id="numChapters"
            type="number"
            value={numChapters}
            onChange={(e) => setNumChapters(parseInt(e.target.value))}
            min="1"
          />
        </div>
        <div className="form-group">
          <label htmlFor="plot">Plot:</label>
          <textarea
            id="plot"
            value={plot}
            onChange={(e) => setPlot(e.target.value)}
            placeholder="Describe the main events and storyline"
          />
        </div>
        <div className="form-group">
          <label htmlFor="writingStyle">Writing Style:</label>
          <input
            id="writingStyle"
            type="text"
            value={writingStyle}
            onChange={(e) => setWritingStyle(e.target.value)}
            placeholder="e.g., descriptive, concise, humorous"
          />
        </div>
        <div className="form-group">
          <label htmlFor="styleGuide">Style Guide:</label>
          <textarea
            id="styleGuide"
            value={styleGuide}
            onChange={(e) => setStyleGuide(e.target.value)}
            placeholder="Any specific guidelines for the writing"
          />
        </div>
        <div className="form-group">
          <label htmlFor="minWordCount">Minimum Word Count:</label>
          <input
            id="minWordCount"
            type="number"
            value={minWordCount}
            onChange={(e) => setMinWordCount(parseInt(e.target.value))}
            min="0"
          />
        </div>
        <div className="form-group">
          <label htmlFor="additionalInstructions">Additional Instructions:</label>
          <textarea
            id="additionalInstructions"
            value={additionalInstructions}
            onChange={(e) => setAdditionalInstructions(e.target.value)}
            placeholder="Any other details or requirements"
          />
        </div>
        <button type="submit" disabled={isGenerating} className="submit-button">
          {isGenerating ? 'Generating...' : 'Generate Chapter'}
        </button>
      </form>
      {streamedContent && (
        <div className="generated-content">
          <h3>Generated Content:</h3>
          <pre className="generated-text">{streamedContent}</pre>
        </div>
      )}
    </div>
  );
};

export default CreateChapter;
