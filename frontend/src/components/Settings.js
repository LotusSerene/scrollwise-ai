import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Settings.css';
import { getAuthHeaders } from '../utils/auth';

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
    checkApiKey();
    fetchModelSettings();
  }, []);

  const checkApiKey = async () => {
    try {
      const response = await axios.get('/api/check-api-key', { headers: getAuthHeaders() });
      setIsKeySet(response.data.isSet);
      setApiKey(response.data.apiKey || '');
    } catch (error) {
      console.error('Error checking API key:', error);
    }
  };

  const fetchModelSettings = async () => {
    try {
      const response = await axios.get('/api/model-settings', { headers: getAuthHeaders() });
      setModelSettings(response.data);
    } catch (error) {
      console.error('Error fetching model settings:', error);
    }
  };

  const handleSaveApiKey = async () => {
    try {
      await axios.post('/api/save-api-key', { apiKey }, { headers: getAuthHeaders() });
      setMessage('API key saved successfully');
      setIsKeySet(true);
      setIsEditing(false);
    } catch (error) {
      setMessage('Error saving API key');
    }
  };

  const handleRemoveApiKey = async () => {
    try {
      await axios.delete('/api/remove-api-key', { headers: getAuthHeaders() });
      setMessage('API key removed successfully');
      setIsKeySet(false);
      setApiKey('');
    } catch (error) {
      setMessage('Error removing API key');
    }
  };

  const handleSaveModelSettings = async () => {
    try {
      await axios.post('/api/model-settings', modelSettings, { headers: getAuthHeaders() });
      setMessage('Model settings saved successfully');
    } catch (error) {
      setMessage('Error saving model settings');
    }
  };

  const handleModelChange = (setting, value) => {
    setModelSettings(prev => ({ ...prev, [setting]: value }));
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
    <div className="settings">
      <h2>Settings</h2>
      <div className="api-key-section">
        <h3>API Key</h3>
        {isKeySet && !isEditing ? (
          <>
            <p>API Key: {apiKey}</p>
            <button onClick={() => setIsEditing(true)}>Edit API Key</button>
            <button onClick={handleRemoveApiKey}>Remove API Key</button>
          </>
        ) : (
          <>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your API key"
            />
            <button onClick={handleSaveApiKey}>Save API Key</button>
          </>
        )}
      </div>
      <div className="model-settings-section">
        <h3>Model Settings</h3>
        {Object.entries(modelSettings).map(([setting, value]) => (
          <div key={setting}>
            <label>{setting}:</label>
            <select
              value={value}
              onChange={(e) => handleModelChange(setting, e.target.value)}
            >
              {(setting === 'embeddingsModel' ? embeddingsOptions : modelOptions).map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
        ))}
        <button onClick={handleSaveModelSettings}>Save Model Settings</button>
      </div>
      {message && <p className="message">{message}</p>}
    </div>
  );
}

export default Settings;
