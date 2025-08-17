"use client"
import React, { useState, useEffect } from 'react';
import Inventory from './MaintenanceInventory';
import Staff from './MaintenanceStaff';
import useScheduleStore from '../../../store/useScheduleStore';

const MaintenanceTabs = () => {
    const [tabIndex, setTabIndex] = useState(0);
    const { inventory, staff, fetchData, loading, error } = useScheduleStore();
    const [selectedLocation, setSelectedLocation] = useState('120-B');

    useEffect(() => {
        fetchData(selectedLocation);  
    }, [fetchData, selectedLocation]);

    const handleTabChange = (newValue) => {
        setTabIndex(newValue);
    };

    const handleLocationChange = (location) => {
        setSelectedLocation(location);
    };

    return (
        <div>
            <div className="flex justify-center mb-4">
                <div
                    className={`tab ${tabIndex === 0 ? 'bg-[#FEECC8] border-[#FFD700] text-black' : 'border border-gray-300 text-gray-600'} rounded-md min-w-[300px] h-14 px-2 mx-2 text-sm cursor-pointer flex items-center justify-center`}
                    onClick={() => handleTabChange(0)}
                >
                    Inventory
                </div>
                <div
                    className={`tab ${tabIndex === 1 ? 'bg-[#FEECC8] border-[#FFD700] text-black' : 'border border-gray-300 text-gray-600'} rounded-md min-w-[300px] h-14 px-2 mx-2 text-sm cursor-pointer flex items-center justify-center`}
                    onClick={() => handleTabChange(1)}
                >
                    Staff
                </div>
            </div>
            <div className="mx-2.5">
                {tabIndex === 0 && <Inventory data={inventory} loading={loading} error={error} onLocationChange={handleLocationChange} />}
                {tabIndex === 1 && <Staff data={staff} loading={loading} error={error} onLocationChange={handleLocationChange} />}
            </div>
        </div>
    );
};

export default MaintenanceTabs;
