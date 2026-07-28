export function renderYearSelector(years, selectedYear) {
  return `
    <div class="control-group">
      <label for="year-select">Season</label>
      <select id="year-select">
        ${years.map((year) => `
          <option value="${year}" ${year === selectedYear ? "selected" : ""}>Summer ${year}</option>
        `).join("")}
      </select>
    </div>
  `;
}
