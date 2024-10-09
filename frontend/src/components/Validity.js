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
              {check.chapterId}
            </li>
          ))}
        </ul>
      </div>
      <div className="validity-content">
        {selectedCheck && (
          <div className="validity-details">
            <h3>{selectedCheck.chapterId}</h3>
            <p><strong>Is Valid:</strong> {selectedCheck.isValid ? 'Yes' : 'No'}</p>
            <p><strong>Feedback:</strong> {selectedCheck.feedback || 'No feedback available'}</p>
            <p><strong>Review Feedback:</strong> {selectedCheck.reviewFeedback || 'No review feedback available'}</p>
            <p><strong>Style Guide Feedback:</strong> {selectedCheck.styleGuideFeedback || 'No style guide feedback available'}</p>
            <p><strong>Continuity Feedback:</strong> {selectedCheck.continuityFeedback || 'No continuity feedback available'}</p>
            <p><strong>Adheres to Style Guide:</strong> {selectedCheck.adheresToStyleGuide ? 'Yes' : 'No'}</p>
            <p><strong>Continuity:</strong> {selectedCheck.continuity ? 'Yes' : 'No'}</p>
            <h4>Test Results:</h4>
            {selectedCheck.testResults && selectedCheck.testResults.length > 0 ? (
              <ul>
                {selectedCheck.testResults.map((result, index) => (
                  <li key={index}>{result}</li>
                ))}
              </ul>
            ) : (
              <p>No test results available</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default Validity;
