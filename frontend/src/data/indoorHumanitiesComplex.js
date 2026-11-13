const BUILDINGS = [
  { id: 'education', name: '사범관' },
  { id: 'business', name: '상경관' },
  { id: 'humanity', name: '인문관' },
]

const FLOORS = [1, 2, 3, 4, 5]

const makeNode = (id, name, buildingId, floor, kind) => ({
  id,
  name,
  buildingId,
  floor,
  kind,
  indoor: true,
})

const makeEdge = (id, from, to, overrides = {}) => ({
  id,
  from,
  to,
  kind: 'indoor_path',
  distance: null,
  estimatedTime: null,
  walkingDistance: null,
  stairs: false,
  ramp: null,
  wheelchairAccessible: true,
  lighting: 'indoor',
  transport: 'walk',
  available: true,
  bidirectional: true,
  ...overrides,
})

const indoorNodes = []
const indoorEdges = []

BUILDINGS.forEach(({ id, name }) => {
  FLOORS.forEach((floor) => {
    indoorNodes.push(
      makeNode(`${id}JunctionF${floor}`, `${name} ${floor}층 내부 분기점`, id, floor, 'junction'),
      makeNode(`${id}ElevatorF${floor}`, `${name} ${floor}층 엘리베이터`, id, floor, 'elevator'),
      makeNode(`${id}StairF${floor}`, `${name} ${floor}층 계단`, id, floor, 'stair'),
    )

    indoorEdges.push(
      makeEdge(
        `${id}-f${floor}-junction-elevator`,
        `${id}JunctionF${floor}`,
        `${id}ElevatorF${floor}`,
      ),
      makeEdge(
        `${id}-f${floor}-junction-stair`,
        `${id}JunctionF${floor}`,
        `${id}StairF${floor}`,
      ),
    )
  })

  indoorNodes.push(
    makeNode(`${id}EntranceF1`, `${name} 1층 출입구`, id, 1, 'entrance'),
  )

  indoorEdges.push(
    makeEdge(
      `${id}-f1-entrance-junction`,
      `${id}EntranceF1`,
      `${id}JunctionF1`,
    ),
  )

  FLOORS.slice(0, -1).forEach((floor) => {
    const nextFloor = floor + 1

    indoorEdges.push(
      makeEdge(
        `${id}-elevator-f${floor}-f${nextFloor}`,
        `${id}ElevatorF${floor}`,
        `${id}ElevatorF${nextFloor}`,
        {
          kind: 'elevator',
          walkingDistance: 0,
          transport: 'elevator',
        },
      ),
      makeEdge(
        `${id}-stair-f${floor}-f${nextFloor}`,
        `${id}StairF${floor}`,
        `${id}StairF${nextFloor}`,
        {
          kind: 'stairs',
          stairs: true,
          wheelchairAccessible: false,
          transport: 'walk',
        },
      ),
    )
  })
})

// 1층에서는 세 건물 사이를 실내로 이동할 수 없다.
// 2~5층에서만 사범관↔상경관, 상경관↔인문관 통로를 연결한다.
FLOORS.filter((floor) => floor >= 2).forEach((floor) => {
  const educationBusinessPassage = `educationBusinessPassageF${floor}`
  const businessHumanityPassage = `businessHumanityPassageF${floor}`

  indoorNodes.push(
    makeNode(
      educationBusinessPassage,
      `사범관·상경관 ${floor}층 연결통로`,
      null,
      floor,
      'indoor_passage',
    ),
    makeNode(
      businessHumanityPassage,
      `상경관·인문관 ${floor}층 연결통로`,
      null,
      floor,
      'indoor_passage',
    ),
  )

  indoorEdges.push(
    makeEdge(
      `education-f${floor}-education-business-passage`,
      `educationJunctionF${floor}`,
      educationBusinessPassage,
    ),
    makeEdge(
      `business-f${floor}-education-business-passage`,
      `businessJunctionF${floor}`,
      educationBusinessPassage,
    ),
    makeEdge(
      `business-f${floor}-business-humanity-passage`,
      `businessJunctionF${floor}`,
      businessHumanityPassage,
    ),
    makeEdge(
      `humanity-f${floor}-business-humanity-passage`,
      `humanityJunctionF${floor}`,
      businessHumanityPassage,
    ),
  )
})

export const indoorHumanitiesComplex = {
  status: 'mock',
  notes: [
    '인문관·상경관·사범관 내부 이동 구조용 Mock 데이터입니다.',
    '1층에서는 세 건물끼리 실내로 연결되지 않습니다.',
    '2층부터 5층까지는 사범관-상경관-인문관 순서로 실내 연결됩니다.',
    '각 건물의 1~5층에는 엘리베이터와 계단이 모두 있습니다.',
    '확인되지 않은 거리와 예상 이동시간은 null입니다.',
  ],
  buildings: BUILDINGS,
  floors: FLOORS,
  nodes: indoorNodes,
  edges: indoorEdges,
}

export { indoorNodes, indoorEdges }
