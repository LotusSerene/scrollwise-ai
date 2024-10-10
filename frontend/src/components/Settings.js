import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Settings.css';
import { getAuthToken } from '../utils/auth';

function Settings() {
  const [apiKey, setApiKey] = useState('');
  const [message, setMessage] = useState('');
  const [isKeySet, setIsKeySet] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [modelSettings, setModelSettings] = useState({
    mainLLM: 'gemini-1.5-pro-002',
    checkLLM: 'gemini-1.5-pro-002',
    embeddingsModel: 'models/text-embedding-004',
    titleGenerationLLM: 'gemini-1.5-pro-002',
    characterExtractionLLM: 'gemini-1.5-pro-002',
    knowledgeBaseQueryLLM: 'gemini-1.5-pro-002'
  });

  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      checkApiKeyStatus();
      fetchModelSettings();
    } else {
      setMessage('Please log in to access settings.');
    }
  }, []);

  const checkApiKeyStatus = async () => {
    try {
      const token = getAuthToken();
      if (!token) {
        setMessage('Authentication token is missing. Please log in again.');
        return;
      }
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/check-api-key`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setIsKeySet(response.data.isSet);
      if (response.data.isSet) {
        setApiKey(response.data.apiKey);
      }
    } catch (error) {
      console.error('Error checking API key status:', error);
      if (error.response && error.response.status === 401) {
        setMessage('Your session has expired. Please log in again.');
      } else {
        setMessage('Error checking API key status. Please try again later.');
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const token = getAuthToken();
      if (!token) {
        setMessage('Authentication token is missing. Please log in again.');
        return;
      }
      const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/save-api-key`, { apiKey }, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setMessage(response.data.message);
      setIsKeySet(true);
      setIsEditing(false);
      checkApiKeyStatus(); // Refresh the masked API key
    } catch (error) {
      console.error('Error saving API key:', error);
      if (error.response && error.response.status === 401) {
        setMessage('Your session has expired. Please log in again.');
      } else {
        setMessage('Error saving API key. Please try again later.');
      }
    }
  };

  const handleRemove = async () => {
    try {
      const token = getAuthToken();
      if (!token) {
        setMessage('Authentication token is missing. Please log in again.');
        return;
      }
      const response = await axios.delete(`${process.env.REACT_APP_API_URL}/api/remove-api-key`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setMessage(response.data.message);
      setIsKeySet(false);
      setApiKey('');
    } catch (error) {
      console.error('Error removing API key:', error);
      if (error.response && error.response.status === 401) {
        setMessage('Your session has expired. Please log in again.');
      } else {
        setMessage('Error removing API key. Please try again later.');
      }
    }
  };

  const fetchModelSettings = async () => {
    try {
      const token = getAuthToken();
      if (!token) {
        setMessage('Authentication token is missing. Please log in again.');
        return;
      }
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/model-settings`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setModelSettings(response.data);
    } catch (error) {
      console.error('Error fetching model settings:', error);
      if (error.response && error.response.status === 401) {
        setMessage('Your session has expired. Please log in again.');
      } else {
        setMessage('Error fetching model settings. Please try again later.');
      }
    }
  };

  const handleModelSettingChange = (setting, value) => {
    setModelSettings(prev => ({ ...prev, [setting]: value }));
  };

  const saveModelSettings = async () => {
    try {
      const token = getAuthToken();
      if (!token) {
        setMessage('Authentication token is missing. Please log in again.');
        return;
      }
      await axios.post(`${process.env.REACT_APP_API_URL}/api/model-settings`, modelSettings, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setMessage('Model settings saved successfully');
    } catch (error) {
      console.error('Error saving model settings:', error);
      if (error.response && error.response.status === 401) {
        setMessage('Your session has expired. Please log in again.');
      } else {
        setMessage('Error saving model settings. Please try again later.');
      }
    }
  };

  const modelOptions = [
    { value: 'gemini-1.5-pro-002', label: 'Gemini 1.5 Pro' },
    { value: 'gemini-1.5-flash-002', label: 'Gemini 1.5 Flash' },
    { value: 'gemini-1.5-flash-8b', label: 'Gemini 1.5 Flash 8B' }
  ];

  const embeddingsOptions = [
    { value: 'models/text-embedding-004', label: 'Text Embedding 004' },
    { value: 'models/embedding-001', label: 'Text Embedding 001' }
  ];

  return (
    <div className="settings-container">
      <h2>Settings</h2>
      {message && <p className="message">{message}</p>}
      {!isKeySet && <p className="warning">Please set your API key to use the application.</p>}
      {isKeySet && !isEditing ? (
        <div>
          <p>Your API key is set:</p>
          <p className="api-key-display">{apiKey}</p>
          <button onClick={() => setIsEditing(true)}>Edit API Key</button>
          <button onClick={handleRemove}>Remove API Key</button>
        </div>
      ) : (
        <form onSubmit={handleSubmit}>
          <label htmlFor="apiKey">API Key:</label>
          <input
            type="password"
            id="apiKey"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
          <button type="submit">{isKeySet ? 'Update API Key' : 'Save API Key'}</button>
          {isEditing && <button type="button" onClick={() => setIsEditing(false)}>Cancel</button>}
        </form>
      )}
      
      <h3>Model Settings</h3>
      {Object.entries(modelSettings).map(([key, value]) => (
        <div key={key}>
          <label>{key}:</label>
          {key === 'embeddingsModel' ? (
            <select
              value={value}
              onChange={(e) => handleModelSettingChange(key, e.target.value)}
            >
              {embeddingsOptions.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          ) : (
            <select
              value={value}
              onChange={(e) => handleModelSettingChange(key, e.target.value)}
            >
              {modelOptions.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          )}
        </div>
      ))}
      <button onClick={saveModelSettings}>Save Model Settings</button>
    </div>
  );
}

export default Settings;