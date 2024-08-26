import React, { forwardRef, useImperativeHandle, useState } from "react";
import Select from "react-select";
import "./AgGridStyles.css";

const AgGridMultiSelectEditor = forwardRef((props, ref) => {
  const [selectedOptions, setSelectedOptions] = useState(
    props.value ? props.value.map((value) => ({ value, label: value })) : []
  );

  const onChange = (selectedOptions) => {
    setSelectedOptions(selectedOptions || []);
  };

  useImperativeHandle(ref, () => ({
    getValue() {
      return selectedOptions.map((option) => option.value);
    },
    isPopup() {
      return true;
    },
  }));

  const options = props.options ? props.options.map((option) => ({ value: option, label: option })) : [];

  return (
    <Select
      value={selectedOptions}
      onChange={onChange}
      options={options}
      isMulti
      closeMenuOnSelect={false}
      className="ag-grid-multi-select"
    />
  );
});

export default AgGridMultiSelectEditor;
