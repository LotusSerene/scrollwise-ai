import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './Editor.css';
import { getAuthToken } from '../utils/auth';
import { v4 as uuidv4 } from 'uuid';

function Editor({ chapters, setChapters }) {
  const [selectedChapter, setSelectedChapter] = useState(null);
  const [chapterContent, setChapterContent] = useState(''); 
  const [chapterTitle, setChapterTitle] = useState('');  
  const [error, setError] = useState(null);

  const fetchChapters = useCallback(async () => {
    try {
      const token = getAuthToken();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/chapters`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setChapters(response.data.chapters);
      logging.debug(`Fetched ${response.data.chapters.length} chapters`);
    } catch (error) {
      console.error('Error fetching chapters:', error);
      setError('Error fetching chapters. Please try again later.');
    }
  }, [setChapters]);

  useEffect(() => {
    fetchChapters();
  }, [fetchChapters]);

  const handleChapterClick = (chapter) => {
    setSelectedChapter(chapter);
    setChapterTitle(chapter.title);  
    setChapterContent(chapter.content); 
  };

  const handleCreateChapter = () => {
    setSelectedChapter(null);
    setChapterTitle('');
    setChapterContent('');
  };

  const handleSaveChapter = async () => {
    if (!chapterTitle) { 
      setError('Chapter title is required.');
      return;
    }

    const token = getAuthToken();
    const chapterId = selectedChapter ? selectedChapter.id : uuidv4();

    try {
      if (selectedChapter) {
        // Update existing chapter
        await axios.put(`${process.env.REACT_APP_API_URL}/api/chapters/${chapterId}`, {
          title: chapterTitle,  
          content: chapterContent   
        }, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
      } else {
        // Create new chapter
        const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/chapters`, {
          title: chapterTitle,
          content: chapterContent  
        }, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        // Set the newly created chapter as the selected chapter to prevent duplicate creation
        setSelectedChapter(response.data);
      }

      fetchChapters();
      setError(null);
    } catch (error) {
      console.error('Error saving chapter:', error);
      setError('Error saving chapter. Please try again later.');
    }
  };

  const handleDeleteChapter = async (chapterId) => {
    try {
      const token = getAuthToken();
      await axios.delete(`${process.env.REACT_APP_API_URL}/api/chapters/${chapterId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      fetchChapters();
    } catch (error) {
      console.error('Error deleting chapter:', error);
      setError('Error deleting chapter. Please try again later.');
    }
  };

  return (
    <div className="editor-container">
      <div className="chapter-list">
        <h3>Chapters</h3>
        <ul>
          {chapters.map((chapter) => (
            <li
              key={chapter.id}
              className={selectedChapter && selectedChapter.id === chapter.id ? 'selected' : ''}
              onClick={() => handleChapterClick(chapter)}
            >
          
              {chapter.title}  
              <button onClick={() => handleDeleteChapter(chapter.id)}>Delete</button>
            </li>
          ))}
        </ul>
        <button onClick={handleCreateChapter}>Create New Chapter</button>
      </div>
      <div className="editor-content">
        <h3>{selectedChapter ? `Edit Chapter: ${selectedChapter.title}` : 'Create New Chapter'}</h3>  {/* Reversed: Use chapter.content for title. This is due to a bug where the state variables were swapped. */}
        {error && <p className="error">{error}</p>}
        <label>
          Title:
          <input
            type="text"
            value={chapterTitle} 
            onChange={(e) => setChapterTitle(e.target.value)}
          />
        </label>
        <label>
          Content:
          <textarea
            value={chapterContent}
            onChange={(e) => setChapterContent(e.target.value)}
            rows={20}
            cols={80}
          />
        </label>
        <button onClick={handleSaveChapter}>{selectedChapter ? 'Save' : 'Create'}</button>
      </div>
    </div>
  );
}

export default Editor;
