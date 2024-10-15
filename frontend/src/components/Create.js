// frontend/src/components/Create.js
import React, { useState, useEffect } from 'react';
import { getAuthHeaders } from '../utils/auth';
import { toast } from 'react-toastify';
import './Create.css'; // We'll create this file for styling
import Header from './Header'; // Import the Header component

const CreateChapter = ({ onChapterGenerated }) => {
  const [numChapters, setNumChapters] = useState(1);
  const [plot, setPlot] = useState('');
  const [writingStyle, setWritingStyle] = useState('');
  const [styleGuide, setStyleGuide] = useState('');
  const [minWordCount, setMinWordCount] = useState(1000);
  const [additionalInstructions, setAdditionalInstructions] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [streamedContent, setStreamedContent] = useState('');
  const [presets, setPresets] = useState([]);
  const [isFetchingPresets, setIsFetchingPresets] = useState(true);
  const [selectedPreset, setSelectedPreset] = useState('');
  const [newPresetName, setNewPresetName] = useState('');

  useEffect(() => {
    const fetchPresets = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_API_URL}/presets/`, {
          headers: getAuthHeaders(),
        });
        const data = await response.json();
        setPresets(data);
      } catch (error) {
        console.error('Error fetching presets:', error);
        toast.error('Error fetching presets');
      } finally {
        setIsFetchingPresets(false);
      }
    };

    fetchPresets();
  }, []);

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
              toast.success('All chapters generated successfully');
              setIsGenerating(false);
              break;
            } else if (data.error) {
              toast.error(`Error: ${data.error}`);
              setIsGenerating(false);
            }
          } catch (err) {
            console.error("Error parsing chunk:", err);
          }
        }
        
        if (done) break;
      }
    } catch (error) {
      console.error('Error generating chapters:', error);
      toast.error('Error generating chapters');
      setIsGenerating(false);
    }
  };

  const handleSavePreset = async () => {
    try {
      const requestBody = {
        name: newPresetName,
        data: {
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
        }
      };


      const response = await fetch(`${process.env.REACT_APP_API_URL}/presets/`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (response.ok) {
        const data = await response.json();
        setPresets([...presets, data]);
        setNewPresetName('');
        toast.success('Preset saved successfully');
      } else {
        const errorData = await response.json();
        let errorMessage = 'Unknown error occurred';
        if (errorData.detail) {
          errorMessage = typeof errorData.detail === 'string' 
            ? errorData.detail 
            : JSON.stringify(errorData.detail);
        }
        console.error('Error response:', errorData);
        toast.error(`Error saving preset: ${errorMessage}`);
      }
    } catch (error) {
      console.error('Error saving preset:', error);
      toast.error(`Error saving preset: ${error.message || 'Unknown error occurred'}`);
    }
  };

  const handleLoadPreset = (presetId) => {
    console.log("Loading preset with ID:", presetId);
    const presetIdNum = parseInt(presetId, 10);
    if (isNaN(presetIdNum)) {
      console.error("Invalid preset ID:", presetId);
      return;
    }
    setSelectedPreset(presetIdNum);
    const preset = presets.find(p => p.id === presetIdNum);
    if (preset && preset.data) {
      setNumChapters(preset.data.numChapters || 1);
      setPlot(preset.data.plot || '');
      setWritingStyle(preset.data.writingStyle || '');
      setStyleGuide(preset.data.styleGuide || '');
      setMinWordCount(preset.data.minWordCount || 1000);
      setAdditionalInstructions(preset.data.additionalInstructions || '');
    } else {
      console.error("Preset or preset data not found");
    }
  };

  const handleDeletePreset = async (e, presetId) => {
    e.stopPropagation();
    console.log("Deleting preset with ID:", presetId);
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/presets/${presetId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });

      if (response.ok) {
        setPresets(presets.filter(p => p.id !== parseInt(presetId)));
        setSelectedPreset('');
        toast.success('Preset deleted successfully');
      } else {
        const errorData = await response.json();
        console.error('Error response:', errorData);
        toast.error(`Error deleting preset: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error deleting preset:', error);
      toast.error('Error deleting preset');
    }
  };

  return (
    <div className="create-container">
      <Header isGenerating={isGenerating} />
      <div className="presets-container">
        <div className="form-group">
          <label htmlFor="presets">Presets:</label>
          <select 
            id="presets" 
            value={selectedPreset} 
            onChange={(e) => handleLoadPreset(e.target.value)}
            disabled={isFetchingPresets}
          >
            <option value="">Select a preset</option>
            {Array.isArray(presets) && presets.map(preset => {
              return (
                <option key={preset.id} value={preset.id}>
                  {preset.name}
                </option>
              );
            })}
          </select>
          {isFetchingPresets && <p key="loading">Loading presets...</p>}
          {selectedPreset && (
            <button 
              type="button" 
              onClick={(e) => handleDeletePreset(e, selectedPreset)} 
              className="delete-preset-button"
            >
              Delete
            </button>
          )}
        </div>

        <div className="form-group">
          <label htmlFor="newPresetName">Save Preset:</label>
          <input
            type="text"
            id="newPresetName"
            value={newPresetName}
            onChange={(e) => setNewPresetName(e.target.value)}
            placeholder="Preset name"
          />
          <button type="button" onClick={handleSavePreset} disabled={!newPresetName}>
            Save
          </button>
        </div>
      </div> {/* End of presets-container */}

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
