import React, { useState, useEffect } from 'react';
import { Button, TextField, Typography, Paper, List, ListItem, ListItemText, Divider } from '@mui/material';
import axios from 'axios';
import { getAuthHeaders } from '../utils/auth';

const KnowledgeBase = () => {
  const [knowledgeBaseContent, setKnowledgeBaseContent] = useState([]);
  const [textInput, setTextInput] = useState('');
  const [file, setFile] = useState(null);

  useEffect(() => {
    fetchKnowledgeBaseContent();
  }, []);

  const fetchKnowledgeBaseContent = async () => {
    try {
      const headers = getAuthHeaders();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, { headers });
      setKnowledgeBaseContent(response.data.content);
    } catch (error) {
      console.error('Error fetching knowledge base content:', error);
    }
  };

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    try {
      const headers = getAuthHeaders();
      await axios.post(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, 
        { documents: [textInput] },
        { headers }
      );
      setTextInput('');
      fetchKnowledgeBaseContent();
    } catch (error) {
      console.error('Error adding text to knowledge base:', error);
    }
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const headers = getAuthHeaders();
      headers['Content-Type'] = 'multipart/form-data';
      await axios.post(`${process.env.REACT_APP_API_URL}/api/upload-document`, formData, { headers });
      setFile(null);
      fetchKnowledgeBaseContent();
    } catch (error) {
      console.error('Error uploading document:', error);
    }
  };

  return (
    <Paper elevation={3} style={{ padding: '20px', marginTop: '20px' }}>
      <Typography variant="h5" gutterBottom>Knowledge Base</Typography>
      
      <Typography variant="h6" gutterBottom>Current Knowledge Base Content</Typography>
      <List>
        {knowledgeBaseContent.map((item, index) => (
          <React.Fragment key={index}>
            <ListItem>
              <ListItemText
                primary={`Type: ${item.type}`}
                secondary={
                  <>
                    <Typography component="span" variant="body2" color="textPrimary">
                      Content: {item.content}
                    </Typography>
                    <br />
                    <Typography component="span" variant="body2" color="textSecondary">
                      Metadata: {JSON.stringify(item.metadata)}
                    </Typography>
                  </>
                }
              />
            </ListItem>
            {index < knowledgeBaseContent.length - 1 && <Divider />}
          </React.Fragment>
        ))}
      </List>

      <Typography variant="h6" gutterBottom style={{ marginTop: '20px' }}>Add to Knowledge Base</Typography>
      <form onSubmit={handleTextSubmit}>
        <TextField
          fullWidth
          multiline
          rows={4}
          variant="outlined"
          label="Add text to knowledge base"
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          style={{ marginBottom: '10px' }}
        />
        <Button type="submit" variant="contained" color="primary">
          Add Text
        </Button>
      </form>

      <form onSubmit={handleFileUpload} style={{ marginTop: '20px' }}>
        <input
          type="file"
          onChange={(e) => setFile(e.target.files[0])}
          style={{ marginBottom: '10px' }}
        />
        <Button type="submit" variant="contained" color="secondary">
          Upload Document
        </Button>
      </form>
    </Paper>
  );
};

export default KnowledgeBase;
