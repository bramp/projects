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
package main

import (
	"testing"
)

func TestParseLocation2(t *testing.T) {
	tests := []struct {
		in                string
		wantLat, wantLong float64
	}{
		{
			in: `7255 Mission St
			Daly City, CA 94014
			(37.69253191000007, -122.46503693799997)`,
			wantLat:  37.69253191000007,
			wantLong: -122.46503693799997,
		},
	}

	for _, test := range tests {
		lat, long, err := parseLocation2(test.in)
		if err != nil {
			t.Errorf("parseLocation2(%q) err = %s want nil", test.in, err)
			continue
		}
		if lat != test.wantLat || long != test.wantLong {
			t.Errorf("parseLocation2(%q) = (%f, %f) want (%f, %f)", test.in, lat, long, test.wantLat, test.wantLong)
		}
	}
}
