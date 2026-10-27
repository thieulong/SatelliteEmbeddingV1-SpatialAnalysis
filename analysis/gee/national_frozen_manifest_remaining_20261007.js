// Complete fixed-coordinate recovery batch after the 2026-10-07 stability gate.
//
// Coordinates are copied from the frozen canonical manifests:
//   SE:  se_point_stability_20261007_A.csv
//   TAS: tas_point_stability_20261007_B.csv
//
// The preceding two-cell fixed-coordinate batch passed identity and numerical
// QA. This script contains every remaining canonical point: 130 SE points in
// 19 fine cells and two Tasmania points in one fine cell. It deliberately does
// not call ee.FeatureCollection.randomPoints. The 20 spatial tasks may be
// queued together; every CSV remains unverified until retrieved and checked.

var RUN = '20260930';
var RECOVERY = '20261007';
var FOLDER = 'AusHabitat_Pilot_' + RUN + '_Recovery_20261005';
var DATA = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL');
var BOUNDARY = ee.FeatureCollection(
  'projects/satellite-embedding-analysis/assets/AusHabitat_mainland_Tas_GAUL2015_pilot_v1');
var WC = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map');
var YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024];
var CRS = 'EPSG:3577';
var TRANSFORM = [10, 0, 0, 0, -10, 0];
var PROJECTION = ee.Projection(CRS, TRANSFORM);
var N = 200;

var FRAMES = {
  SE: {bounds: [134, -40, 154, -30], seed: 20260935},
  TAS: {bounds: [143, -44, 149, -40], seed: 20260936}
};

var RECOVERY_PARTS = [
  {
    "name": "SE_FINE_00_02",
    "stratum": "SE",
    "bounds": [
      134.0,
      -35.0,
      136.5,
      -32.5
    ],
    "points": [
      [
        "SE_64",
        134.69191780727786,
        -32.85684210516777
      ],
      [
        "SE_75",
        135.87281512752864,
        -33.44090783780219
      ],
      [
        "SE_92",
        136.0790515329361,
        -34.35095653391675
      ],
      [
        "SE_131",
        134.3165792273594,
        -33.05189039378856
      ],
      [
        "SE_139",
        135.66739090430687,
        -33.25142032583882
      ],
      [
        "SE_188",
        134.8785427919664,
        -32.89826227656976
      ]
    ]
  },
  {
    "name": "SE_FINE_01_01",
    "stratum": "SE",
    "bounds": [
      136.5,
      -37.5,
      139.0,
      -35.0
    ],
    "points": [
      [
        "SE_4",
        137.69141360683366,
        -35.09679764027168
      ]
    ]
  },
  {
    "name": "SE_FINE_01_02",
    "stratum": "SE",
    "bounds": [
      136.5,
      -35.0,
      139.0,
      -32.5
    ],
    "points": [
      [
        "SE_2",
        138.49409062775362,
        -33.96417330383667
      ],
      [
        "SE_20",
        136.51505921392425,
        -33.738663661051355
      ],
      [
        "SE_36",
        138.32580418266215,
        -32.57492780122446
      ],
      [
        "SE_38",
        138.5367249542145,
        -34.23575722980567
      ],
      [
        "SE_85",
        136.8379210238925,
        -33.08678743949886
      ],
      [
        "SE_91",
        136.5106977512448,
        -32.6978116048255
      ],
      [
        "SE_100",
        136.8112233858381,
        -33.63962408444544
      ],
      [
        "SE_121",
        138.64020651138284,
        -33.274827064122945
      ],
      [
        "SE_192",
        137.79133754053467,
        -34.869806338104915
      ]
    ]
  },
  {
    "name": "SE_FINE_02_00",
    "stratum": "SE",
    "bounds": [
      139.0,
      -40.0,
      141.5,
      -37.5
    ],
    "points": [
      [
        "SE_14",
        140.33532057265697,
        -37.62885040718441
      ],
      [
        "SE_172",
        141.366534519561,
        -37.54116011704195
      ]
    ]
  },
  {
    "name": "SE_FINE_02_01",
    "stratum": "SE",
    "bounds": [
      139.0,
      -37.5,
      141.5,
      -35.0
    ],
    "points": [
      [
        "SE_55",
        141.2732676374241,
        -35.623766651852286
      ],
      [
        "SE_58",
        140.82681791155116,
        -35.25940410056724
      ],
      [
        "SE_94",
        141.37421048917722,
        -36.97325518447506
      ],
      [
        "SE_95",
        139.76194992740747,
        -35.5327641629003
      ],
      [
        "SE_167",
        140.78602976603707,
        -37.081610024312894
      ],
      [
        "SE_197",
        139.66629161603677,
        -35.20500047886661
      ]
    ]
  },
  {
    "name": "SE_FINE_02_02",
    "stratum": "SE",
    "bounds": [
      139.0,
      -35.0,
      141.5,
      -32.5
    ],
    "points": [
      [
        "SE_0",
        140.3248343944006,
        -34.44116530608819
      ],
      [
        "SE_7",
        139.66174804454786,
        -32.67772859813428
      ],
      [
        "SE_51",
        141.07706894363412,
        -32.53279227980477
      ],
      [
        "SE_93",
        140.7996021499552,
        -34.54732655606162
      ],
      [
        "SE_103",
        141.40291282340752,
        -32.7660508108553
      ],
      [
        "SE_105",
        141.01115994725012,
        -34.26404930234022
      ],
      [
        "SE_111",
        140.3785115745058,
        -32.524144895893464
      ],
      [
        "SE_128",
        139.8158852004673,
        -32.84887757145923
      ],
      [
        "SE_149",
        140.54885385950558,
        -32.800225991302696
      ],
      [
        "SE_181",
        140.0414040392897,
        -33.27302612618347
      ]
    ]
  },
  {
    "name": "SE_FINE_02_03",
    "stratum": "SE",
    "bounds": [
      139.0,
      -32.5,
      141.5,
      -30.0
    ],
    "points": [
      [
        "SE_3",
        141.06006491161102,
        -31.101075760823147
      ],
      [
        "SE_18",
        140.51160504513606,
        -31.66981623713215
      ],
      [
        "SE_32",
        139.78240172444208,
        -31.65297409453333
      ],
      [
        "SE_42",
        139.7015601889663,
        -31.048453548046044
      ],
      [
        "SE_79",
        139.75193713944742,
        -31.157827977314778
      ],
      [
        "SE_157",
        141.2022837950418,
        -31.800687518862777
      ],
      [
        "SE_163",
        140.63232102520053,
        -32.20463380918303
      ],
      [
        "SE_179",
        141.30187754848245,
        -30.443233100525852
      ],
      [
        "SE_183",
        139.99654200797227,
        -31.567858079638793
      ]
    ]
  },
  {
    "name": "SE_FINE_03_00",
    "stratum": "SE",
    "bounds": [
      141.5,
      -40.0,
      144.0,
      -37.5
    ],
    "points": [
      [
        "SE_27",
        142.7526350744652,
        -37.74951862614644
      ],
      [
        "SE_39",
        143.6429188723243,
        -37.677097217313424
      ],
      [
        "SE_45",
        143.29073284825807,
        -38.396940438338945
      ],
      [
        "SE_87",
        142.06961768681407,
        -37.502220919132654
      ],
      [
        "SE_136",
        142.89812265680487,
        -37.71747508103067
      ]
    ]
  },
  {
    "name": "SE_FINE_03_01",
    "stratum": "SE",
    "bounds": [
      141.5,
      -37.5,
      144.0,
      -35.0
    ],
    "points": [
      [
        "SE_60",
        143.14300506903874,
        -35.16400823696994
      ],
      [
        "SE_106",
        143.1042723039321,
        -36.41133092220294
      ],
      [
        "SE_113",
        143.69047210318163,
        -35.01168055831013
      ],
      [
        "SE_135",
        141.5435195822153,
        -35.18030121717894
      ],
      [
        "SE_140",
        142.25680601799195,
        -36.03820624559252
      ],
      [
        "SE_171",
        143.01536983505005,
        -36.0516104167669
      ],
      [
        "SE_187",
        143.60668822112035,
        -36.29245159381928
      ],
      [
        "SE_198",
        142.0055979173949,
        -35.03197538422375
      ]
    ]
  },
  {
    "name": "SE_FINE_03_02",
    "stratum": "SE",
    "bounds": [
      141.5,
      -35.0,
      144.0,
      -32.5
    ],
    "points": [
      [
        "SE_9",
        142.13091416440938,
        -34.10038285035709
      ],
      [
        "SE_17",
        141.7076811999666,
        -34.38691720638821
      ],
      [
        "SE_19",
        143.88050010234466,
        -33.10979589150105
      ],
      [
        "SE_34",
        143.58481801688222,
        -33.94549830532861
      ],
      [
        "SE_65",
        143.72164896506607,
        -33.74039427677789
      ],
      [
        "SE_66",
        142.83592022274112,
        -34.62833205379208
      ],
      [
        "SE_74",
        143.89287897572618,
        -33.605430351323314
      ],
      [
        "SE_133",
        142.70450877465507,
        -32.97788886127579
      ],
      [
        "SE_142",
        143.56870956558032,
        -33.03405713140215
      ],
      [
        "SE_145",
        143.3981879668939,
        -33.08579024490808
      ],
      [
        "SE_176",
        143.074181742953,
        -33.445144084648106
      ]
    ]
  },
  {
    "name": "SE_FINE_04_00",
    "stratum": "SE",
    "bounds": [
      144.0,
      -40.0,
      146.5,
      -37.5
    ],
    "points": [
      [
        "SE_5",
        146.4803417802625,
        -38.27405568312037
      ],
      [
        "SE_15",
        144.04270124470156,
        -37.725963687758906
      ],
      [
        "SE_37",
        144.24893508858713,
        -37.573959867322934
      ],
      [
        "SE_115",
        145.19141454208892,
        -38.149361185276945
      ],
      [
        "SE_160",
        145.32348667983254,
        -38.10086712629231
      ],
      [
        "SE_166",
        145.61276340327868,
        -38.600439616911665
      ],
      [
        "SE_175",
        146.19837934197352,
        -38.801897097850286
      ]
    ]
  },
  {
    "name": "SE_FINE_04_03",
    "stratum": "SE",
    "bounds": [
      144.0,
      -32.5,
      146.5,
      -30.0
    ],
    "points": [
      [
        "SE_40",
        144.90347075677084,
        -31.10272300780265
      ],
      [
        "SE_71",
        144.45844797226215,
        -30.69253952194854
      ],
      [
        "SE_86",
        144.25858569848475,
        -30.47702825832164
      ],
      [
        "SE_97",
        144.2850833198097,
        -31.98399141281929
      ],
      [
        "SE_101",
        145.61337523308907,
        -31.478278501033905
      ],
      [
        "SE_110",
        145.37410857745903,
        -30.732878707745783
      ],
      [
        "SE_117",
        144.2965804848114,
        -31.20338326174663
      ],
      [
        "SE_124",
        145.1393062155447,
        -30.32908277450667
      ],
      [
        "SE_132",
        145.54906509812227,
        -32.02308840806056
      ],
      [
        "SE_146",
        144.25346496275282,
        -30.43928078790809
      ],
      [
        "SE_189",
        145.1982609594904,
        -30.49498634948469
      ]
    ]
  },
  {
    "name": "SE_FINE_05_00",
    "stratum": "SE",
    "bounds": [
      146.5,
      -40.0,
      149.0,
      -37.5
    ],
    "points": [
      [
        "SE_52",
        146.65182185058038,
        -38.586147106234286
      ],
      [
        "SE_69",
        146.9084832322273,
        -37.71033298215547
      ],
      [
        "SE_120",
        148.5670590422039,
        -37.52455042104598
      ],
      [
        "SE_168",
        148.56940168633542,
        -37.73631160348407
      ]
    ]
  },
  {
    "name": "SE_FINE_05_01",
    "stratum": "SE",
    "bounds": [
      146.5,
      -37.5,
      149.0,
      -35.0
    ],
    "points": [
      [
        "SE_26",
        147.89718909174252,
        -37.079241898563154
      ],
      [
        "SE_28",
        148.28556923501995,
        -35.53129972626777
      ],
      [
        "SE_47",
        146.6834011006616,
        -36.47748919675086
      ],
      [
        "SE_68",
        147.30384439464507,
        -36.73657861146652
      ],
      [
        "SE_147",
        147.19939821055166,
        -37.173589779248935
      ],
      [
        "SE_148",
        147.40915410302642,
        -35.719884950720086
      ],
      [
        "SE_153",
        148.30796377672485,
        -35.42611005874451
      ],
      [
        "SE_161",
        147.3710542736029,
        -35.04012869062723
      ]
    ]
  },
  {
    "name": "SE_FINE_05_03",
    "stratum": "SE",
    "bounds": [
      146.5,
      -32.5,
      149.0,
      -30.0
    ],
    "points": [
      [
        "SE_6",
        147.58568803961947,
        -30.203653382373773
      ],
      [
        "SE_21",
        148.93397706839698,
        -30.25958443035037
      ],
      [
        "SE_43",
        147.09720745201716,
        -30.18810155383107
      ],
      [
        "SE_62",
        146.9957511052244,
        -30.642487275152384
      ],
      [
        "SE_78",
        146.86950074198504,
        -31.789939358496344
      ],
      [
        "SE_89",
        147.95995772260866,
        -31.06632912623032
      ],
      [
        "SE_96",
        148.5800358595111,
        -31.05692912234722
      ],
      [
        "SE_156",
        147.59476687380965,
        -32.19954962654901
      ],
      [
        "SE_194",
        147.36018447693078,
        -32.355012174805566
      ]
    ]
  },
  {
    "name": "SE_FINE_06_02",
    "stratum": "SE",
    "bounds": [
      149.0,
      -35.0,
      151.5,
      -32.5
    ],
    "points": [
      [
        "SE_61",
        149.46283459946355,
        -34.0774273101739
      ],
      [
        "SE_104",
        150.24557243626117,
        -34.58051935769844
      ],
      [
        "SE_152",
        150.96066209688138,
        -34.068858560916944
      ],
      [
        "SE_182",
        149.7390753409391,
        -33.12240508411212
      ]
    ]
  },
  {
    "name": "SE_FINE_06_03",
    "stratum": "SE",
    "bounds": [
      149.0,
      -32.5,
      151.5,
      -30.0
    ],
    "points": [
      [
        "SE_1",
        151.16545852255905,
        -32.1232273417377
      ],
      [
        "SE_13",
        149.55893999779056,
        -31.63402077111008
      ],
      [
        "SE_31",
        150.50935234337314,
        -30.914513956679748
      ],
      [
        "SE_53",
        149.26591241415204,
        -30.30691461237869
      ],
      [
        "SE_67",
        149.55776571516157,
        -30.51261517543773
      ],
      [
        "SE_108",
        150.67063351058266,
        -30.763544968576213
      ],
      [
        "SE_118",
        151.32746363821096,
        -31.218235707030033
      ],
      [
        "SE_123",
        151.34363503892902,
        -30.065732978211756
      ],
      [
        "SE_137",
        151.49976330035165,
        -31.82545101382087
      ],
      [
        "SE_185",
        150.2949287407653,
        -31.872979950595553
      ]
    ]
  },
  {
    "name": "SE_FINE_07_02",
    "stratum": "SE",
    "bounds": [
      151.5,
      -35.0,
      154.0,
      -32.5
    ],
    "points": [
      [
        "SE_180",
        151.59993155283198,
        -32.97341560976393
      ]
    ]
  },
  {
    "name": "SE_FINE_07_03",
    "stratum": "SE",
    "bounds": [
      151.5,
      -32.5,
      154.0,
      -30.0
    ],
    "points": [
      [
        "SE_10",
        152.3693993850781,
        -30.926537134182457
      ],
      [
        "SE_22",
        151.57991200497383,
        -31.711820754320488
      ],
      [
        "SE_29",
        152.01685210797123,
        -32.156597243947296
      ],
      [
        "SE_35",
        152.00713600125258,
        -30.12323556929296
      ],
      [
        "SE_99",
        152.53963438183771,
        -30.92937593998774
      ],
      [
        "SE_107",
        152.6918346293172,
        -30.752392291244327
      ],
      [
        "SE_112",
        152.57754626225915,
        -30.894839223936582
      ],
      [
        "SE_127",
        151.89559075088212,
        -31.87716972316209
      ],
      [
        "SE_159",
        152.10226585049094,
        -31.499017746114383
      ]
    ]
  },
  {
    "name": "TAS_FINE_01_00",
    "stratum": "TAS",
    "bounds": [
      144.5,
      -44,
      146.0,
      -43
    ],
    "points": [
      [
        "TAS_39",
        145.79813967727117,
        -43.06169481525221
      ],
      [
        "TAS_103",
        145.89609098826165,
        -43.02968473907264
      ]
    ]
  }
];

var DIST_NAMES = [
  'endpoint', 'd2017', 'd2018', 'd2019',
  'd2020', 'd2021', 'd2022', 'd2023'
];

function source(year, roi) {
  return DATA.filterDate(year + '-01-01', (year + 1) + '-01-01')
    .filterBounds(roi).sort('system:index');
}

function stack(roi) {
  var annual = YEARS.map(function(year) {
    return source(year, roi).mosaic().select('A.*');
  });
  var valid = annual.map(function(image, index) {
    return image.mask().reduce(ee.Reducer.min()).unmask(0, false)
      .rename('v' + YEARS[index]);
  });
  function distance(left, right, name) {
    return right.subtract(left).pow(2).reduce(ee.Reducer.sum()).sqrt()
      .rename(name).unmask(-9999, false);
  }
  var distances = [distance(annual[0], annual[7], 'endpoint')];
  for (var index = 0; index < 7; index++) {
    distances.push(distance(annual[index], annual[index + 1],
      'd' + YEARS[index]));
  }
  var diagnostics = [
    annual[0].pow(2).reduce(ee.Reducer.sum()).sqrt().rename('norm2017'),
    annual[7].pow(2).reduce(ee.Reducer.sum()).sqrt().rename('norm2024'),
    annual[0].multiply(annual[7]).reduce(ee.Reducer.sum())
      .rename('dot_endpoint')
  ];
  return ee.Image.cat(distances.concat(valid))
    .addBands(ee.Image.cat(diagnostics).unmask(-9999, false))
    .addBands(WC.unmask(0, false).rename('worldcover2021'))
    .addBands(ee.Image.pixelLonLat());
}

function frameArea(stratum) {
  var spec = FRAMES[stratum];
  return BOUNDARY.geometry().intersection(
    ee.Geometry.Rectangle(spec.bounds, null, false), 100)
    .area(100).divide(1e6);
}

function fixedPoints(part) {
  var area = frameArea(part.stratum);
  var seed = FRAMES[part.stratum].seed;
  return ee.FeatureCollection(part.points.map(function(point) {
    return ee.Feature(ee.Geometry.Point([point[1], point[2]]), {
      stratum: part.stratum,
      point_id: point[0],
      frame_km2: area,
      n_requested: N,
      sample_weight_km2: area.divide(N),
      seed: seed,
      original_lon: point[1],
      original_lat: point[2],
      recovery_method: 'frozen_manifest_fixed_coordinate_recovery',
      recovery_part: part.name,
      manifest_date: RECOVERY
    });
  }));
}

var selectors = [
  'stratum', 'point_id', 'frame_km2', 'n_requested', 'sample_weight_km2',
  'seed', 'original_lon', 'original_lat', 'recovery_method', 'recovery_part',
  'manifest_date'
].concat(DIST_NAMES)
  .concat(['v2017', 'v2018', 'v2019', 'v2020', 'v2021', 'v2022',
    'v2023', 'v2024', 'norm2017', 'norm2024', 'dot_endpoint',
    'worldcover2021', 'longitude', 'latitude']);

RECOVERY_PARTS.forEach(function(part) {
  var cell = ee.Geometry.Rectangle(part.bounds, null, false);
  var samples = stack(cell).reduceRegions({
    collection: fixedPoints(part),
    reducer: ee.Reducer.first(),
    crs: PROJECTION,
    tileScale: 4
  });
  Export.table.toDrive({
    collection: samples,
    description: 'AU_' + RUN + '_frozen_remaining_' + part.name,
    folder: FOLDER,
    fileNamePrefix: 'frozen_remaining_' + part.name,
    fileFormat: 'CSV',
    selectors: selectors
  });
  print(part.name + ' frozen point count', fixedPoints(part).size());
});

print('Complete frozen-manifest remainder: 20 tasks / 132 points.');
