"use client";
import React, { useEffect, useState } from 'react';
import useTurboFanStore from '../../../store/useTurboFanStore';
import { v4 as uuidv4 } from 'uuid';
import HealthPerformanceChart from "./HealthPerformanceChart";

const TurboFanTable = ({ data }) => {
  const [graphPosition, setGraphPosition] = useState(null);
  const [highlightedValue, setHighlightedValue] = useState(null);
  const [adjustment, setAdjustment] = useState({ top: 0, left: 0 });

  const {
    selectedTurboEngine,
    selectedDateRange,
    selectedStatuses,
    statusDropdownOpen,
    searchQuery,
    setSelectedTurboEngine,
    setSelectedDateRange,
    setSelectedStatuses,
    setStatusDropdownOpen,
    setSearchQuery,
  } = useTurboFanStore();

  useEffect(() => {
    if (data && data.rul_predictions && data.rul_predictions.length > 0) {
      setSelectedTurboEngine("all");
    }
  }, [data, setSelectedTurboEngine]);

  const handleTurboEngineChange = (event) => {
    setSelectedTurboEngine(event.target.value);
  };

  const handleDateChange = (name, date) => {
    setSelectedDateRange((prevRange) => ({
      ...prevRange,
      [name]: date,
    }));
  };

  const handleStatusChange = (event) => {
    const { value, checked } = event.target;
    if (checked) {
      setSelectedStatuses([...selectedStatuses, value]);
    } else {
      setSelectedStatuses(selectedStatuses.filter((status) => status !== value));
    }
    setStatusDropdownOpen(false);
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
        return 'text-green-600';
      case 'repair':
        return 'text-red-600';
      case 'caution':
        return 'text-yellow-600';
      default:
        return 'text-gray-900';
    }
  };

  const getEngineLifeClass = (engineLife) => {
    return parseInt(engineLife) < 18 ? 'text-red-600' : '';
  };

  const filteredFiles = data?.rul_predictions?.filter((file) => {
    return (
      (selectedTurboEngine === "all" || file.engine_id?.toString() === selectedTurboEngine) &&
      (selectedStatuses.length === 0 || selectedStatuses.includes(file.engine_status)) &&
      file.engine_id?.toString().includes(searchQuery)
    );
  });

  const handleCellClick = (event, file, value) => {
    const rect = event.target.getBoundingClientRect();
    setGraphPosition({
      top: rect.bottom + window.scrollY + adjustment.top,
      left: rect.left + window.scrollX + adjustment.left,
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

  return (
    <div className="relative mt-8 p-4 border-2 border-gray-800 rounded-lg">
      <div className="mb-4 flex gap-2 justify-end">
        <div>
          <select
            value={selectedTurboEngine}
            onChange={handleTurboEngineChange}
            className="h-6 text-xs block w-full pl-2 pr-8 py-0.5 text-black border border-black focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-xs"
          >
            <option value="all" className="h-6 text-xs bg-white">All Turbo Engines</option>
            {data?.rul_predictions?.map((engine) => (
              <option key={`option-${uuidv4()}`} value={engine.engine_id} className="h-6 text-xs bg-white">
                Turbo Engine {engine.engine_id}
              </option>
            ))}
          </select>
        </div>
      </div>


      {data?.rul_predictions?.length === 0 ? (
        <div className="text-center text-gray-500">No data available</div>
      ) : (
        <div>
          <table className="min-w-full divide-y divide-gray-200 bg-white shadow-md border border-gray-800 relative">
            <thead className="bg-[#679436]">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-white uppercase tracking-wider border-r border-gray-800">
                  <div className="relative">
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={handleSearchQueryChange}
                      placeholder="Search location"
                      className="h-6 w-full pl-2 pr-2 py-0.5 text-black border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-xs"
                    />
                  </div>
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-white uppercase tracking-wider border-r border-gray-800">
                  Predicted Engine Life
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-white uppercase tracking-wider border-r border-gray-800">
                  <div className="relative inline-block text-left">
                    <button
                      type="button"
                      onClick={toggleStatusDropdown}
                      className="inline-flex items-center h-6 text-xs font-medium text-white uppercase tracking-wider focus:outline-none"
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
                      <div className="origin-top-left absolute left-0 mt-2 w-60 rounded-sm shadow-lg bg-[#C7CDBE] ring-1 ring-black ring-opacity-5 z-50">
                        <div className="py-1" role="menu" aria-orientation="vertical" aria-labelledby="status-menu">
                          {['Healthy', 'Repair', 'Caution'].map((status) => (
                            <label key={`status-${status}`} className="flex items-center px-3 py-1 text-xs text-gray-700 hover:bg-gray-100 hover:text-gray-900">
                              <input
                                type="checkbox"
                                value={status}
                                checked={selectedStatuses.includes(status)}
                                onChange={handleStatusChange}
                                className="form-checkbox h-3 w-3 text-indigo-600 focus:ring-indigo-500 border-gray-300"
                              />
                              <span className="ml-2">{status}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredFiles?.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-2 whitespace-nowrap text-sm text-gray-500 text-center">
                    No data available
                  </td>
                </tr>
              ) : (
                filteredFiles?.map((file) => (
                  <tr key={`file-${file.engine_id}`}>
                    <td className="px-1 py-1 whitespace-nowrap text-sm border-r border-gray-800 last:border-r-0 table-cell cursor-pointer"
                        onClick={(event) => handleCellClick(event, file, file.pred_rul)}>
                      <div className="bg-white border p-1 shadow-sm" style={{ margin: '1px' }}>
                        {file.engine_id}
                      </div>
                    </td>
                    <td className="px-1 py-1 whitespace-nowrap text-sm border-r border-gray-800 last:border-r-0 table-cell cursor-pointer"
                        onClick={(event) => handleCellClick(event, file, file.pred_rul)}>
                      <span className={getEngineLifeClass(parseInt(file.pred_rul))}>
                        {file.pred_rul}
                      </span>
                    </td>
                    <td className="px-1 py-1 whitespace-nowrap text-sm font-semibold border-r border-gray-800 last:border-r-0">
                      <span className={getStatusClass(file.engine_status)}>
                        {file.engine_status}
                      </span>
                    </td>
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
                transform: 'translateY(-276%)',
                width: '350px',
                height: '250px',
              }}
            >
              <HealthPerformanceChart data={graphPosition.data} highlightedValue={highlightedValue} />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TurboFanTable;
