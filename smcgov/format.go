// Copyright 2017 Google Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Format takes the Restaurant_Health_Inspections.csv and formats it
// for Google Maps.
//
// TODO
// Perhaps Merge locations at the same address (which have changed names)
//  BANGKOK BAY INC - CONDITIONAL PASS (YELLOW)
//   825 EL CAMINO REAL, REDWOOD CITY, 94063
//
//  BANGKOK BAY THAI CUISINE - CONDITIONAL PASS (YELLOW)
//   825 EL CAMINO REAL, REDWOOD CITY, 94063
//
//    SAKURA 2 - PASS (GREEN)
//      373 MAIN ST, REDWOOD CITY, 94063
//    Koto Japanese Steakhouse - NOT APPLICABLE
//      373 Main St, Redwood City, 94063
//
//
package main

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/infogulch/uniq"
)

const (
	dateFormat = "01/02/2006"
	indexFiles = 4   // Number of index files
	dataFiles  = 100 // Number of data files
)

var (
	location2Rx = regexp.MustCompile(`\((\-?\d+.\d+), (\-?\d+.\d+)\)$`)

	// Keep the below insync with the index.html javascript
	resultsCode = map[int]string{
		0:  "NOT APPLICABLE",
		1:  "MEETS STANDARDS",
		2:  "FAILED TO MEET STANDARDS",
		5:  "FAILED MCL - SELENIUM",
		10: "FAILED ACTION LEVEL SP ORGANIC",
		35: "NOT IN USE",
		49: "PASS (GREEN)",
		50: "CONDITIONAL PASS (YELLOW)",
		51: "EXCELLENT",
		52: "GOOD",
		53: "FAIR",
		54: "POOR",
		55: "CLOSED (RED)",
		80: "VIOLATIONS CORRECTED",
		99: "MAJOR VIOLATION CORRECTED",
	}
	violationStatus = map[string]string{
		"A":  "AREA OF CONCERN",
		"CO": "CORRECTED ON SITE",
		"CV": "VIOLATION CORRECTED",
		"IN": "IN COMPLIANCE",
		"NA": "NOT APPLICABLE",
		"NO": "NOT OBSERVED",
		"NV": "No Viol Observed",
		"OU": "OUT OF COMPLIANCE",
		"UD": "Undetermined",
		"UN": "UNANSWERED",
		"V":  "VIOLATION",
	}
	violationDegree = map[int]string{
		0: "",
		1: "Major",
		2: "Minor",
		3: "Critical/Major",
		6: "Legal Action",
		8: "Food Handler Certification",
	}
)

type Violation struct {
	Description string
	Degree      int `json:",omitempty"`
	Status      string
}

func (v *Violation) String() string {
	return fmt.Sprintf("%s %s (%s)", v.Status, v.Description, v.Degree)
}

// Violations implements the sort.Interface
type Violations []*Violation

func (v Violations) Len() int           { return len(v) }
func (v Violations) Swap(i, j int)      { v[i], v[j] = v[j], v[i] }
func (v Violations) Less(i, j int) bool { return v[i].Description < v[j].Description }

type Inspection struct {
	Date   ShortTime
	Result int
	Reason string

	Violations []*Violation `json:",omitempty"`
}

type Location struct {
	Id                 string `json:",omitempty"`
	Name               string `json:",omitempty"`
	Address, City, Zip string `json:",omitempty"`
	Lat, Long          float64

	LastDate       ShortTime
	LastResult     int
	LastViolations int

	Inspections []*Inspection             `json:",omitempty"`
	inspections map[time.Time]*Inspection `json:"-"`
}

type ShortTime struct {
	time.Time
}

func (t ShortTime) MarshalJSON() ([]byte, error) {
	return []byte(fmt.Sprintf("%q", t.Format("2006-01-02"))), nil
}

type MergeKey struct {
	Name, Address, Zip string
}

// javaHashCode returns the Java string hashcode for the given string.
// Taken from https://www.manniwood.com/2016_03_20/fun_with_java_string_hashing.html
func javaHashCode(s string) int {
	h := 0
	for i := 0; i < len(s); i++ {
		h = 31*h + int(s[i])
	}
	return h
}

func parseLocation2(in string) (float64, float64, error) {
	m := location2Rx.FindStringSubmatch(in)
	if m == nil {
		return 0, 0, fmt.Errorf("no latitude and longitude data")
	}

	lat, err := strconv.ParseFloat(m[1], 64)
	if err != nil {
		return 0, 0, err
	}
	long, err := strconv.ParseFloat(m[2], 64)
	if err != nil {
		return 0, 0, err
	}

	return lat, long, nil
}

func interfaceLen(data interface{}) int {
	switch reflect.TypeOf(data).Kind() {
	case reflect.Slice, reflect.Map:
		return reflect.ValueOf(data).Len()
	}
	return 1
}

func writeJsFile(filename, callback string, data interface{}) error {
	f, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer f.Close()

	if _, err := io.WriteString(f, callback+"("); err != nil {
		return err
	}

	e := json.NewEncoder(f)
	e.SetIndent("", "  ")
	if err := e.Encode(data); err != nil {
		return err
	}

	if _, err := io.WriteString(f, ")"); err != nil {
		return err
	}

	fmt.Fprintf(os.Stderr, "Wrote %q (%d records)\n", filename, interfaceLen(data))

	return nil
}

func writeData(locationsMap map[string]*Location) error {
	var dataMap []map[string]*Location
	for i := 0; i < dataFiles; i++ {
		dataMap = append(dataMap, make(map[string]*Location))
	}

	for id, location := range locationsMap {
		dataMap[javaHashCode(id)%len(dataMap)][id] = location
	}

	for i, locations := range dataMap {
		filename := fmt.Sprintf("data/data-%02d.js", i)
		if err := writeJsFile(filename, "locationCallback", locations); err != nil {
			return err
		}
	}

	return nil
}

// writeIndex writes out the index js files. It deletes data from the locationMap
// as it goes, so don't try and use locationMap afterwards.
func writeIndex(locationsMap map[string]*Location) error {
	// Convert the map into an array, filter, and sort.
	var locations = make([]*Location, 0, len(locationsMap))

	for _, location := range locationsMap {
		// Clear all the fields we don't want in the index.
		location.Address = ""
		location.City = ""
		location.Zip = ""
		location.Inspections = nil

		if location.Lat == 0 && location.Long == 0 {
			// Skip rows we don't do anything useful.
			continue
		}

		locations = append(locations, location)
	}
	sort.Slice(locations, func(i, j int) bool {
		// Sort South-to-North, so the markers are drawn bottom up, making sure
		// they overlap correctly.
		return locations[i].Lat > locations[j].Lat
	})

	for i := 0; i < indexFiles; i++ {
		filename := fmt.Sprintf("data/index-%d.js", i)
		from := i * len(locations) / indexFiles
		to := (i + 1) * len(locations) / indexFiles

		if err := writeJsFile(filename, "locationIndexCallback", locations[from:to]); err != nil {
			return err
		}
	}

	return nil
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "%s <input>\n", filepath.Base(os.Args[0]))
		os.Exit(1)
	}

	f, err := os.Open(os.Args[1])
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open input: %s\n", err)
	}

	r := csv.NewReader(f)

	header, err := r.Read()
	if err == io.EOF {
		fmt.Fprintf(os.Stderr, "Failed to read header: %s\n", err)
	}

	var rows, skipped, noLocation int

	dups := make(map[MergeKey]string)       // keyed by name/address
	locations := make(map[string]*Location) // keyed by ID

	for {
		row, err := r.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			fmt.Fprintf(os.Stderr, "Failed to read row: %s\n", err)
		}
		rows++

		record := make(map[string]string)
		for i, name := range header {
			record[name] = row[i]
		}

		id := record["Location ID"]
		if id == "" {
			fmt.Fprintf(os.Stderr, "Skipping row %d with invalid ID %q\n", rows, id)
			skipped++
			continue
		}

		key := MergeKey{
			Name:    strings.ToLower(strings.TrimSpace(record["Location Name"])),
			Address: strings.ToLower(strings.TrimSpace(record["Address"])),
			Zip:     strings.TrimSpace(record["Zip"]),
		}

		if dupid, found := dups[key]; found {
			id = dupid
		} else {
			dups[key] = id
		}

		l, found := locations[id]
		if !found {
			l = &Location{
				Id:          id,
				inspections: make(map[time.Time]*Inspection),
			}
			locations[id] = l
		}

		date, err := time.Parse(dateFormat, record["Activity Date"])
		if err != nil {
			fmt.Fprintf(os.Stderr, "Skipping row %d with invalid date %q: %s", rows, record["Activity Date"], err)
			skipped++
			continue
		}

		if l.LastDate.Before(date) {
			// Keep the most recent info
			l.Name = strings.TrimSpace(record["Location Name"])
			l.Address = strings.TrimSpace(record["Address"])
			l.City = strings.TrimSpace(record["City"])
			l.Zip = strings.TrimSpace(record["Zip"])
			l.LastDate = ShortTime{date}

			if record["Location 2"] != "" {
				lat, long, err := parseLocation2(record["Location 2"])
				if err != nil {
					//fmt.Fprintf(os.Stderr, "Failed to parse location 2 %q: %s\n", record["Location 2"], err)
				} else {
					l.Lat = lat
					l.Long = long
				}
			}

			if l.Lat == 0 && l.Long == 0 {
				noLocation++
			}
		}

		inspection, found := l.inspections[date]
		if !found {
			code, err := strconv.Atoi(record["Result Code"])
			if err != nil {
				fmt.Fprintf(os.Stderr, "Skipping row %d with unparsable Inspection Result Code %q\n", rows, record["Result Code"])
				skipped++
				continue
			}
			if _, found := resultsCode[code]; !found {
				fmt.Fprintf(os.Stderr, "Skipping row %d with unknown Inspection Result Code %d\n", rows, code)
				skipped++
				continue
			}

			inspection = &Inspection{
				Date:   ShortTime{date},
				Result: code, // Description in record["Inspection Result"]
				Reason: record["Service Code Description"],
			}

			l.inspections[date] = inspection
		}

		// Filter out some codes, in particular CA02 has gibberish in the Description field
		code := record["Violation Code"]
		if code != "CA02" {
			// Filter out particular violation status (such as in complaince, N/A, etc)
			status := strings.TrimSpace(record["Violation Status"])

			if status != "" && status != "IN" && status != "NA" && status != "UN" && status != "NO" && status != "NV" {
				if _, found := violationStatus[status]; !found {
					fmt.Fprintf(os.Stderr, "Skipping row %d with unknown Violation Status %q\n", rows, status)
					skipped++
					continue
				}

				degree := 0
				if record["Violation Degree Code"] != "" {
					degree, err = strconv.Atoi(record["Violation Degree Code"])
					if err != nil {
						fmt.Fprintf(os.Stderr, "Skipping row %d with unparsable Violation Degree Code %q\n", rows, record["Violation Degree Code"])
						skipped++
						continue
					}
				}

				if _, found := violationDegree[degree]; !found {
					fmt.Fprintf(os.Stderr, "Skipping row %d with unknown Violation Degree Code %d\n", rows, degree)
					skipped++
					continue
				}

				inspection.Violations = append(inspection.Violations, &Violation{
					Description: record["Violation Description"],
					Degree:      degree, // record["Violation Degree"],
					Status:      status, // record["Violation Status Description"],
				})
			}
		}
	}

	// Reformat Locations
	for _, location := range locations {
		inspections := make([]*Inspection, 0, 0) // I always want a empty slice instead of nil
		for _, inspection := range location.inspections {

			violations := inspection.Violations

			// Sort and remove dups (it is unclearly why there are duplicates).
			sort.Sort(Violations(violations))
			inspection.Violations = violations[:uniq.Uniq(Violations(violations))]

			inspections = append(inspections, inspection)
		}
		sort.Slice(inspections, func(i, j int) bool {
			return inspections[j].Date.Before(inspections[i].Date.Time)
		})

		location.inspections = nil
		location.Inspections = inspections

		// Find last none NA score (otherwise set to NA)
		for _, inspection := range inspections {
			if inspection.Result != 0 {
				location.LastResult = inspection.Result
				location.LastViolations = len(inspection.Violations)
				break
			}
		}
		if location.LastResult == 0 && len(inspections) > 0 {
			location.LastResult = inspections[0].Result
			location.LastViolations = len(inspections[0].Violations)
		}
	}

	fmt.Fprintf(os.Stderr, "Read %d rows (%d skipped) %d without location\n", rows, skipped, noLocation)
	fmt.Fprintf(os.Stderr, "Writing %d records\n", len(locations))

	if err := writeData(locations); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write locations data: %s\n", err)
		os.Exit(1)
	}

	if err := writeIndex(locations); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write locations index: %s\n", err)
		os.Exit(1)
	}

}
