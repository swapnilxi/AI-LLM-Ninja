import React from 'react';

export const StaffAvailabilityChip = ({ status, requiredCrew }) => {
    return (
        <div className="flex flex-col items-center gap-0.5 mx-0.5">
            <div className={`text-xs font-normal w-16 h-6 flex items-center justify-center text-black rounded-md ${status >= requiredCrew ? 'bg-[#C2F86B]' : 'bg-[#FC574F]'}`}>
                {status > 0 ? status : 'NA'}
            </div>
        </div>
    );
};

export const InventoryAvailabilityChip = ({ quantity, quantityNeeded }) => {
    return (
        <div className="flex flex-col items-center mx-0.5 gap-0.5">
            <div className={`text-xs font-normal w-16 h-6 flex items-center justify-center text-black rounded-md ${quantity >= quantityNeeded ? 'bg-[#C2F86B]' : 'bg-[#FC574F]'}`}>
                {quantity > 0 ? quantity : 'NA'}
            </div>
        </div>
    );
};
