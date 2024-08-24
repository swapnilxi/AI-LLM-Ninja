import React, { useState, useEffect } from 'react';
import { columns, files, statusOptions } from './data.js';
import { getRULPredictions } from './apiService.js';
import HealthPerformanceChart from './HealthPerformanceChart';

const TableComponent = () => {
  const [selectedTurboEngine, setSelectedTurboEngine] = useState('turboEngine1');
  const [selectedStatuses, setSelectedStatuses] = useState([]);
  const [statusDropdownOpen, setStatusDropdownOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [file, setFile] = useState(null);
  const [predictions, setPredictions] = useState([]);
  const [graphPosition, setGraphPosition] = useState(null);
  const [highlightedValue, setHighlightedValue] = useState(null);

  const handleTurboEngineChange = (event) => {
    setSelectedTurboEngine(event.target.value);
  };

  const handleStatusChange = (event) => {
    const { value, checked } = event.target;
    if (checked) {
      setSelectedStatuses((prevStatuses) => [...prevStatuses, value]);
    } else {
      setSelectedStatuses((prevStatuses) =>
        prevStatuses.filter((status) => status !== value)
      );
    }
  };

  const toggleStatusDropdown = () => {
    setStatusDropdownOpen(!statusDropdownOpen);
  };

  const handleSearchQueryChange = (event) => {
    setSearchQuery(event.target.value);
  };

  const getStatusClass = (status) => {
    switch (status.toLowerCase()) {
      case 'healthy':
        return 'text-green-800';
      case 'repair':
        return 'text-orange-800';
      case 'caution':
        return 'text-red-800';
      default:
        return 'text-gray-900';
    }
  };

  const getEngineLifeClass = (engineLife) => {
    return engineLife < 20 ? 'text-red-600' : '';
  };

  const handleFileChange = (event) => {
    setFile(event.target.files[0]);
  };

  const handleSubmit = async () => {
    if (file) {
      try {
        const response = await getRULPredictions(file);
        setPredictions(response.data.rul_predictions);
      } catch (error) {
        console.error('Error fetching RUL predictions:', error);
      }
    }
  };

  const handleCellClick = (event, file, value) => {
    const rect = event.target.getBoundingClientRect();
    setGraphPosition({
      top: rect.bottom + window.scrollY,
      left: rect.left + window.scrollX,
      data: file,
    });
    setHighlightedValue(value);
  };

  const handleClickOutside = (event) => {
    if (
      graphPosition &&
      !event.target.closest('.graph-container') &&
      !event.target.closest('.table-cell')
    ) {
      setGraphPosition(null);
      setHighlightedValue(null);
    }
  };

  useEffect(() => {
    document.addEventListener('click', handleClickOutside);
    return () => {
      document.removeEventListener('click', handleClickOutside);
    };
  }, [graphPosition]);

  const filteredFiles = files.filter((file) => {
    return (
      file.turboEngine === selectedTurboEngine &&
      (selectedStatuses.length === 0 || selectedStatuses.includes(file.status)) &&
      file.name.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  return (
    <div className="mt-8 p-4 border-2 border-gray-800 rounded-lg">
      <div className="mb-4 flex gap-2 justify-end">
        <div>
          <select
            value={selectedTurboEngine}
            onChange={handleTurboEngineChange}
            className="h-6 text-xs block w-full pl-2 pr-8 py-0.5 text-black border border-black focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-xs"
          >
            <option value="turboEngine1" className="h-6 text-xs bg-white">
              Turbo Engine 1
            </option>
            <option value="turboEngine2" className="h-6 text-xs bg-white">
              Turbo Engine 2
            </option>
          </select>
        </div>
      </div>

      <div className="mb-4">
        <input type="file" onChange={handleFileChange} />
        <button onClick={handleSubmit} className="ml-2 bg-[#679436] text-white p-2 rounded">
          Submit
        </button>
      </div>

      <table className="min-w-full divide-y divide-gray-200 bg-white shadow-md overflow-hidden border border-gray-800">
        <thead className="bg-[#679436]">
          <tr>
            {columns.map((column, columnIndex) => (
              <th
                key={column.uid}
                className="px-4 py-2 text-left text-xs font-medium text-white uppercase tracking-wider border-r border-gray-800 last:border-r-0"
              >
                {column.uid === 'name' ? (
                  <div className="relative">
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={handleSearchQueryChange}
                      placeholder="Search"
                      className="h-6 w-full pl-2 pr-2 py-0.5 text-black border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-xs"
                    />
                  </div>
                ) : column.uid === 'status' ? (
                  <div className="relative inline-block text-left">
                    <button
                      type="button"
                      onClick={toggleStatusDropdown}
                      className="inline-flex items-center h-6 text-xs font-medium text-white uppercase tracking-wider focus:outline-none cursor-pointer"
                      id="status-menu"
                      aria-expanded={statusDropdownOpen}
                      aria-haspopup="true"
                      style={{ padding: '0.5rem', width: '7rem' }}
                    >
                      Status
                      <svg
                        className="ml-1 h-3 w-3"
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        aria-hidden="true"
                      >
                        <path
                          fillRule="evenodd"
                          d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 011.414 1.414l-4 4a1 1 01-1.414 0l-4-4a1 1 010-1.414z"
                          clipRule="evenodd"
                        />
                      </svg>
                    </button>

                    {statusDropdownOpen && (
                      <div className="origin-top-left absolute left-0 mt-2 w-60 rounded-sm shadow-lg bg-[#C7CDBE] ring-1 ring-black ring-opacity-5 z-10">
                        <div className="py-1" role="menu" aria-orientation="vertical" aria-labelledby="status-menu">
                          {statusOptions.map((status) => (
                            <label
                              key={status.uid}
                              className="flex items-center px-3 py-1 text-xs text-gray-700 hover:bg-gray-100 hover:text-gray-900 cursor-pointer"
                            >
                              <input
                                type="checkbox"
                                value={status.uid}
                                checked={selectedStatuses.includes(status.uid)}
                                onChange={handleStatusChange}
                                className="form-checkbox h-3 w-3 text-indigo-600 focus:ring-indigo-500 border-gray-300 cursor-pointer"
                              />
                              <span className="ml-2">{status.name}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  column.name
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {filteredFiles.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-2 whitespace-nowrap text-sm text-gray-500 text-center"
              >
                No data available
              </td>
            </tr>
          ) : (
            filteredFiles.map((file, index) => (
              <tr key={index}>
                {columns.map((column, columnIndex) => (
                  <td
                    key={column.uid}
                    className={`px-1 py-1 whitespace-nowrap text-sm border-r border-gray-800 last:border-r-0 table-cell cursor-pointer ${columnIndex === 0 ? 'bg-white' : ''}`}
                    style={{ width: `${100 / columns.length}%`, height: '40px' }}
                    onClick={(event) => handleCellClick(event, file, file.predictedEngineLife)}
                  >
                    <span
                      className={
                        column.uid === 'predictedEngineLife'
                          ? getEngineLifeClass(file[column.uid])
                          : column.uid === 'status'
                          ? getStatusClass(file[column.uid])
                          : ''
                      }
                    >
                      {file[column.uid]}
                    </span>
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>

      {graphPosition && (
        <div
          className="graph-container absolute bg-white border rounded shadow-lg cursor-pointer"
          style={{
            top: graphPosition.top,
            left: graphPosition.left,
            width: '350px',
            height: '250px',
          }}
        >
          <HealthPerformanceChart data={graphPosition.data} highlightedValue={highlightedValue} />
        </div>
      )}
    </div>
  );
};

export default TableComponent;
