// frontend/src/components/Editor.js
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './Editor.css';
import { getAuthHeaders } from '../utils/auth';
import { v4 as uuidv4 } from 'uuid';

function Editor({ chapters, setChapters }) {
  const [selectedChapter, setSelectedChapter] = useState(null);
  const [chapterContent, setChapterContent] = useState(''); 
  const [chapterTitle, setChapterTitle] = useState('');  
  const [error, setError] = useState(null);
  const logging = {
    debug: (message) => console.debug(message),
  };

  const fetchChapters = useCallback(async () => {
    try {
      const headers = getAuthHeaders();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/chapters`, {
        headers: headers
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

  const handleDeleteChapter = async (chapterId) => {
    try {
      const headers = getAuthHeaders();
      const chapter = chapters.find(ch => ch.id === chapterId);
      const embeddingId = chapter ? chapter.embedding_id : null;

      // Delete the chapter from the normal database using chapterId
      await axios.delete(`${process.env.REACT_APP_API_URL}/api/chapters/${chapterId}`, { headers: headers });

      // Remove chapter from knowledge base using embedding_id
      if (embeddingId) {
        await axios.delete(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, {
          headers: headers,
          data: { embedding_id: embeddingId }
        });
      }

      fetchChapters();
    } catch (error) {
      console.error('Error deleting chapter:', error);
      setError('Error deleting chapter. Please try again later.');
    }
  };

  const handleSaveChapter = async () => {
    if (!chapterTitle) { 
      setError('Chapter title is required.');
      return;
    }

    const headers = getAuthHeaders();
    const chapterId = selectedChapter ? selectedChapter.id : uuidv4();

    try {
      let response;

      if (selectedChapter) {
        // Update existing chapter
        response = await axios.put(`${process.env.REACT_APP_API_URL}/api/chapters/${chapterId}`, {
          title: chapterTitle,  
          content: chapterContent
        }, {
          headers: headers
        });
      } else {
        // Create new chapter
        response = await axios.post(`${process.env.REACT_APP_API_URL}/api/chapters`, {
          title: chapterTitle,
          content: chapterContent
        }, {
          headers: headers
        });
      }

      fetchChapters();
      setError(null);
    } catch (error) {
      console.error('Error saving chapter:', error);
      setError('Error saving chapter. Please try again later.');
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
              <span className="remove-icon" onClick={() => handleDeleteChapter(chapter.id)}>❌</span>
            </li>
          ))}
        </ul>
        <button onClick={handleCreateChapter}>Create New Chapter</button>
      </div>
      <div className="editor-content">
        <h3>{selectedChapter ? `Edit Chapter: ${selectedChapter.title}` : 'Create New Chapter'}</h3>
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
