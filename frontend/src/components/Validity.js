import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './Validity.css';
import { getAuthToken } from '../utils/auth';

function Validity() {
  const [validityChecks, setValidityChecks] = useState([]);
  const [selectedCheck, setSelectedCheck] = useState(null);

  useEffect(() => {
    fetchValidityChecks();
  }, []);

  const fetchValidityChecks = async () => {
    try {
      const token = getAuthToken();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/validity-checks`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setValidityChecks(response.data.validityChecks);
    } catch (error) {
      console.error('Error fetching validity checks:', error);
    }
  };

  const handleCheckClick = (check) => {
    setSelectedCheck(check);
  };

  const handleDeleteCheck = async (checkId) => {
    try {
      const token = getAuthToken();
      await axios.delete(`${process.env.REACT_APP_API_URL}/api/validity-checks/${checkId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      fetchValidityChecks(); // Refresh the list after deletion
      if (selectedCheck && selectedCheck.id === checkId) {
        setSelectedCheck(null);
      }
    } catch (error) {
      console.error('Error deleting validity check:', error);
    }
  };

  return (
    <div className="validity-container">
      <div className="validity-sidebar">
        <h2>Validity Checks</h2>
        <ul>
          {validityChecks.map((check) => (
            <li
              key={check.id}
              className={`validity-check ${selectedCheck && selectedCheck.id === check.id ? 'selected' : ''}`}
              onClick={() => handleCheckClick(check)}
            >
              {check.chapterTitle} : {check.isValid ? 'Valid' : 'Invalid'}
            </li>
          ))}
        </ul>
      </div>
      <div className="validity-content">
        {selectedCheck && (
          <div className="validity-details">
            <h3>{selectedCheck.chapterTitle}</h3>
            <p>Validity: {selectedCheck.isValid ? 'Valid' : 'Invalid'}</p>
            <div className="validity-details-section">
              <p><strong>Chapter ID:</strong> {selectedCheck.chapterId}</p>
              <p><strong>Chapter Title:</strong> {selectedCheck.chapterTitle}</p>
              <p><strong>Validity:</strong> {selectedCheck.isValid ? 'Valid' : 'Invalid'}</p>
              <p><strong>Feedback:</strong> {selectedCheck.feedback}</p>
              <p><strong>Review:</strong> {selectedCheck.review}</p>
              <p><strong>Style Guide Adherence:</strong> {selectedCheck.style_guide_adherence ? 'Yes' : 'No'}</p>
              <p><strong>Style Guide Feedback:</strong> {selectedCheck.style_guide_feedback}</p>
              <p><strong>Continuity:</strong> {selectedCheck.continuity ? 'Yes' : 'No'}</p>
              <p><strong>Continuity Feedback:</strong> {selectedCheck.continuity_feedback}</p>
              <p><strong>Test Results:</strong> {selectedCheck.test_results}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default Validity;
