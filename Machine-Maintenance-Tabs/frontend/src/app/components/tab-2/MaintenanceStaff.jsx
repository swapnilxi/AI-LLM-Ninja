import React, { useState, useEffect } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import { BsCalendar2 } from 'react-icons/bs';
import { StaffAvailabilityChip } from './AvailabilityChips';
import useScheduleStore from '../../../store/useScheduleStore';

const Staff = ({ data, loading, error, onLocationChange }) => {
    const { earliestDate } = useScheduleStore();
    const [selectedSkill, setSelectedSkill] = useState('');
    const [selectedLocation, setSelectedLocation] = useState('');
    const [locationSearch, setLocationSearch] = useState('');
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [selectedDateRange, setSelectedDateRange] = useState({
        start: earliestDate || new Date(),
        end: new Date((earliestDate || new Date()).getTime() + 6 * 24 * 60 * 60 * 1000),
    });
    const [staffData, setStaffData] = useState([]);

    useEffect(() => {
        const fetchStaffData = async () => {
            try {
                const response = await axios.post('http://localhost:5000/sched', {
                    location: selectedLocation
                });
                setStaffData(response.data.staff);
            } catch (error) {
                console.error("Error fetching data", error);
            }
        };

        fetchStaffData();
    }, [selectedLocation, selectedDateRange.start]);

    useEffect(() => {
        if (earliestDate) {
            setSelectedDateRange({
                start: earliestDate,
                end: new Date(earliestDate.getTime() + 6 * 24 * 60 * 60 * 1000),
            });
        }
    }, [earliestDate]);

    const handleDateChange = (name, date) => {
        setSelectedDateRange((prevRange) => {
            const newRange = { ...prevRange, [name]: date };
            if (name === 'start' && date > prevRange.end) {
                newRange.end = date;
            } else if (name === 'end' && date < prevRange.start) {
                newRange.start = date;
            }

            const maxEndDate = new Date(newRange.start);
            maxEndDate.setDate(maxEndDate.getDate() + 6);
            if (newRange.end > maxEndDate) {
                newRange.end = maxEndDate;
            }

            return newRange;
        });
    };

    const handleSkillChange = (event) => {
        setSelectedSkill(event.target.value);
    };

    const handleLocationChange = (location) => {
        setSelectedLocation(location);
        onLocationChange(location);
        setIsDropdownOpen(false);
    };

    const handleSearchChange = (event) => {
        setLocationSearch(event.target.value);
    };

    const toggleDropdown = () => {
        setIsDropdownOpen(!isDropdownOpen);
        setLocationSearch('');
    };

    const filteredLocations = ['120-B', '110-C', '201-A', '101-A'].filter(location =>
        location.toLowerCase().includes(locationSearch.toLowerCase())
    );

    const generateDateRange = (start, end) => {
        const dateRange = [];
        const currentDate = new Date(start);
        const endDate = new Date(end);

        while (currentDate <= endDate) {
            dateRange.push(new Date(currentDate));
            currentDate.setDate(currentDate.getDate() + 1);
        }

        return dateRange.map(date => date.toLocaleDateString('en-GB'));
    };

    const formattedDateRange = generateDateRange(selectedDateRange.start, selectedDateRange.end);

    const getAvailabilityForDate = (availability, date) => {
        const item = availability.find(avail => avail.date === date);
        return item ? item.quantity : 0;
    };

    const parseAvailability = (availability, requiredCrew) => {
        return (
            <div className="flex flex-row justify-center gap-0.5">
                {formattedDateRange.map((date, index) => {
                    const quantity = getAvailabilityForDate(availability, date);
                    return <StaffAvailabilityChip key={index} status={quantity} requiredCrew={requiredCrew} />;
                })}
            </div>
        );
    };

    const filteredData = data.filter(item => 
        (selectedSkill ? item.skill === selectedSkill : true) && 
        (selectedLocation ? item.asset_location === selectedLocation : true)
    );

    const uniqueSkills = [...new Set(data.map(item => `${item.skill}-${item.asset_location}`))];

    const renderTable = (data) => (
        <table className="w-full border-separate border-spacing-y-2">
            <thead>
                <tr>
                    <th className="border border-[#679436] p-2 text-center bg-gray-300 text-black font-normal h-20">Location</th>
                    <th className="border border-[#679436] p-2 text-center bg-gray-300 text-black font-normal h-20">Skills</th>
                    <th className="border border-[#679436] p-2 text-center bg-gray-300 text-black font-normal h-20">
                        Availability
                        <div className="flex flex-row justify-center  mt-2 gap-1.5">
                            {formattedDateRange.map((date, index) => (
                                <div key={index} className="flex flex-col  items-center bg-white rounded-lg">
                                    <div className="text-xs font-normal border border-lime-800 w-16 h-6 flex items-center justify-center rounded-md">
                                        {date}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </th>
                </tr>
            </thead>
            <tbody>
                {data.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                        <td className="border border-[#679436] p-2 text-center text-base h-16">{row.asset_location}</td>
                        <td className="border border-[#679436] p-2 text-center text-base h-16">{row.skill}</td>
                        <td className="border border-[#679436] p-2 text-center text-xs h-16">{parseAvailability(row.availability, row.crew_required)}</td>
                    </tr>
                ))}
            </tbody>
        </table>
    );

    if (loading) {
        return <div>Loading...</div>;
    }

    if (error) {
        return <div>{error}</div>;
    }

    if (!data || data.length === 0) {
        return <div>No data available</div>;
    }

    return (
        <div>
            <div className="flex gap-2 justify-end mb-4">
                <div className="relative h-6 w-36 flex items-center cursor-pointer border border-black">
                    <select
                        value={selectedSkill}
                        onChange={handleSkillChange}
                        className="w-full h-full px-3 text-xs text-black bg-white outline-none appearance-none"
                    >
                        <option value="">Select Skills</option>
                        {uniqueSkills.map(skill => (
                            <option key={skill} value={skill.split('-')[0]}>{skill.split('-')[0]}</option>
                        ))}
                    </select>
                    <span className="absolute right-2 pointer-events-none text-xs">
                        ▼
                    </span>
                </div>
                <div className="relative h-6 w-36 cursor-pointer border border-black">
                    <div className="w-full h-full flex items-center justify-between px-3" onClick={toggleDropdown}>
                        <span className="text-xs text-black">{selectedLocation || "Location"}</span>
                        <span className="pointer-events-none text-xs">▼</span>
                    </div>
                    {isDropdownOpen && (
                        <div className="absolute left-0 right-0 top-full bg-white border border-gray-300 z-10">
                            <input
                                type="text"
                                placeholder="Search location here..."
                                value={locationSearch}
                                onChange={handleSearchChange}
                                className="w-full px-3 py-2 text-xs text-black bg-white outline-none"
                            />
                            {filteredLocations.map(location => (
                                <div
                                    key={location}
                                    onClick={() => handleLocationChange(location)}
                                    className="px-3 py-2 text-xs text-black hover:bg-gray-200 cursor-pointer"
                                >
                                    {location}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
                <div className="relative bg-[#679436] p-1 h-6 w-28 flex items-center cursor-pointer">
                    <BsCalendar2 className="absolute left-2 text-white" />
                    <DatePicker
                        selected={selectedDateRange.start}
                        onChange={(date) => handleDateChange('start', date)}
                        className="w-full pl-6 pr-2 text-xs text-white bg-transparent border-none outline-none cursor-pointer"
                        dateFormat="yyyy-MM-dd"
                    />
                </div>
                <div className="relative bg-[#679436] p-1 h-6 w-28 flex items-center cursor-pointer">
                    <BsCalendar2 className="absolute left-2 text-white" />
                    <DatePicker
                        selected={selectedDateRange.end}
                        onChange={(date) => handleDateChange('end', date)}
                        className="w-full pl-6 pr-2 text-xs text-white bg-transparent border-none outline-none cursor-pointer"
                        dateFormat="yyyy-MM-dd"
                        minDate={selectedDateRange.start}
                        maxDate={new Date(selectedDateRange.start.getTime() + 6 * 24 * 60 * 60 * 1000)}
                    />
                </div>
            </div>
            {renderTable(filteredData)}
        </div>
    );
};

export default Staff;
