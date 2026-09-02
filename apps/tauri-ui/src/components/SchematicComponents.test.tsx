import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const pickKicadProjectMock = vi.fn()
const resolveKicadProjectMock = vi.fn()
const listSchematicComponentsMock = vi.fn()
const componentEnvelopesMock = vi.fn()
const loadProjectMock = vi.fn()
const saveProjectMock = vi.fn()

vi.mock('../lib/kicadProject', () => ({
  pickKicadProject: (...a: unknown[]) => pickKicadProjectMock(...a),
  resolveKicadProject: (...a: unknown[]) => resolveKicadProjectMock(...a),
  listSchematicComponents: (...a: unknown[]) => listSchematicComponentsMock(...a),
  componentEnvelopes: (...a: unknown[]) => componentEnvelopesMock(...a),
}))
vi.mock('../lib/projects', () => ({
  loadProject: (...a: unknown[]) => loadProjectMock(...a),
  saveProject: (...a: unknown[]) => saveProjectMock(...a),
}))

const { SchematicComponents } = await import('./SchematicComponents')

const FILES = {
  project_name: 'Hello_World_Blinky',
  project_dir: '/p',
  pro_path: '/p/Hello_World_Blinky.kicad_pro',
  schematic_path: '/p/Hello_World_Blinky.kicad_sch',
  pcb_path: '/p/Hello_World_Blinky.kicad_pcb',
  sheet_count: 1,
}

/** The real components from the maintainer's own blinky project, including
 *  the CR2032 whose footprint names a .step that does not exist. */
const READ = {
  source_path: FILES.schematic_path,
  read_at: '2026-09-01T23:15:29+00:00',
  components: [
    {
      reference: 'BT1', value: 'Battery_Cell',
      footprint: 'Battery:Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles',
      dnp: false, footprint_found: true,
      model_ref: '${KICAD10_3DMODEL_DIR}/Battery.3dshapes/Battery_Panasonic_CR2032-HFN_Horizontal.step',
      model_path: null, has_model: false,
    },
    {
      reference: 'D1', value: 'LED', footprint: 'LED_THT:LED_D1.8mm_W3.3mm_H2.4mm',
      dnp: false, footprint_found: true, model_ref: 'x', model_path: '/real/led.step', has_model: true,
    },
  ],
}

beforeEach(() => {
  pickKicadProjectMock.mockReset()
  resolveKicadProjectMock.mockReset().mockResolvedValue(FILES)
  listSchematicComponentsMock.mockReset().mockResolvedValue(READ)
  componentEnvelopesMock.mockReset().mockResolvedValue({
    envelopes: [], measured: 1, stated: 1, unknown: 0,
    source_path: FILES.schematic_path, read_at: READ.read_at,
    min_interior_height_mm: 20, tallest: { reference: 'BT1', z_mm: 20, source: 'user' },
  })
  loadProjectMock.mockReset().mockResolvedValue({ name: 'p' })
  saveProjectMock.mockReset().mockResolvedValue({ name: 'p' })
})

describe('SchematicComponents', () => {
  it('says nothing is linked yet, and that KiCad need not be running', async () => {
    render(<SchematicComponents projectName="p" />)
    expect(await screen.findByRole('button', { name: 'Link KiCad project…' })).toBeTruthy()
    expect(screen.getByText(/does not need to be running/)).toBeTruthy()
  })

  it('reads the schematic after a project is picked, and remembers it', async () => {
    pickKicadProjectMock.mockResolvedValue(FILES.pro_path)
    render(<SchematicComponents projectName="p" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Link KiCad project…' }))

    await waitFor(() => expect(listSchematicComponentsMock).toHaveBeenCalledWith(FILES.schematic_path))
    await waitFor(() =>
      expect(saveProjectMock).toHaveBeenCalledWith(
        expect.objectContaining({ kicad_project_path: FILES.pro_path }),
      ),
    )
  })

  it('reloads a previously linked project on mount without asking again', async () => {
    loadProjectMock.mockResolvedValue({ name: 'p', kicad_project_path: FILES.pro_path })
    render(<SchematicComponents projectName="p" />)

    await waitFor(() => expect(resolveKicadProjectMock).toHaveBeenCalledWith(FILES.pro_path))
    expect(pickKicadProjectMock).not.toHaveBeenCalled()
  })

  it('flags a component whose footprint names a 3D model that is not installed', async () => {
    /* The gap that prompted SPEC-325, in the maintainer's own project: the
       CR2032 footprint exists, but the .step it references does not. */
    loadProjectMock.mockResolvedValue({ name: 'p', kicad_project_path: FILES.pro_path })
    render(<SchematicComponents projectName="p" />)

    expect(await screen.findByText('BT1')).toBeTruthy()
    expect(screen.getByText('no 3D model')).toBeTruthy()
    expect(screen.getByText('ready')).toBeTruthy()
    expect(screen.getByText(/1 with no 3D model/)).toBeTruthy()
  })

  it('warns that a multi-sheet list may be incomplete, because that is unverified', async () => {
    /* SPEC-325 §3: no multi-sheet project existed to test against, so
       whether kicad-cli walks the hierarchy is unknown. Saying so beats
       presenting a possibly-partial list as complete. */
    loadProjectMock.mockResolvedValue({ name: 'p', kicad_project_path: FILES.pro_path })
    resolveKicadProjectMock.mockResolvedValue({ ...FILES, sheet_count: 3 })
    render(<SchematicComponents projectName="p" />)

    expect(await screen.findByText(/3 sheets/)).toBeTruthy()
    expect(screen.getByText(/has not been verified/)).toBeTruthy()
  })

  it('says so when a project has no schematic yet, rather than showing an empty table', async () => {
    loadProjectMock.mockResolvedValue({ name: 'p', kicad_project_path: FILES.pro_path })
    resolveKicadProjectMock.mockResolvedValue({ ...FILES, schematic_path: null })
    render(<SchematicComponents projectName="p" />)

    // The message embeds a <code> tag, so the text node is split -- match a
    // contiguous fragment rather than across elements.
    expect(await screen.findByText(/next to its project file yet/)).toBeTruthy()
    expect(listSchematicComponentsMock).not.toHaveBeenCalled()
  })

  it('reports a read failure instead of rendering a stale or empty table', async () => {
    loadProjectMock.mockResolvedValue({ name: 'p', kicad_project_path: FILES.pro_path })
    listSchematicComponentsMock.mockRejectedValue(new Error("kicad-cli's BOM is missing expected column(s)"))
    render(<SchematicComponents projectName="p" />)

    expect(await screen.findByText(/missing expected column/)).toBeTruthy()
    expect(screen.queryByText('BT1')).toBeNull()
  })

  /* SPEC-326. On the maintainer's real board the minimum interior height is
     set by BT1 at 20mm -- the one component with no model -- while the
     tallest measured part is only 15.5mm. Sizing from measured parts alone
     would produce a box the battery does not fit in. */
  it('recommends a minimum interior height and names what set it', async () => {
    loadProjectMock.mockResolvedValue({ name: 'p', kicad_project_path: FILES.pro_path })
    render(<SchematicComponents projectName="p" />)

    expect(await screen.findByText(/at least/)).toBeTruthy()
    expect(screen.getByText('20mm')).toBeTruthy()
    expect(screen.getByText(/height you supplied/)).toBeTruthy()
  })

  it('warns that an unknown height means the real minimum may be taller', async () => {
    loadProjectMock.mockResolvedValue({ name: 'p', kicad_project_path: FILES.pro_path })
    componentEnvelopesMock.mockResolvedValue({
      envelopes: [], measured: 1, stated: 0, unknown: 1,
      source_path: FILES.schematic_path, read_at: READ.read_at,
      min_interior_height_mm: 15.5, tallest: { reference: 'R1', z_mm: 15.5, source: 'model' },
    })
    render(<SchematicComponents projectName="p" />)

    expect(await screen.findByText(/real minimum may be taller/)).toBeTruthy()
  })

  it('offers a height for a footprint with no model, and remembers it by footprint', async () => {
    loadProjectMock.mockResolvedValue({ name: 'p', kicad_project_path: FILES.pro_path })
    render(<SchematicComponents projectName="p" />)

    const input = await screen.findByLabelText(
      'Height for Battery:Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles',
    )
    fireEvent.change(input, { target: { value: '20' } })
    fireEvent.click(screen.getByRole('button', { name: 'set' }))

    await waitFor(() =>
      expect(saveProjectMock).toHaveBeenCalledWith(
        expect.objectContaining({
          component_heights: {
            'Battery:Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles': 20,
          },
        }),
      ),
    )
  })

  it('never offers a height for a component that already has a real model', async () => {
    loadProjectMock.mockResolvedValue({ name: 'p', kicad_project_path: FILES.pro_path })
    render(<SchematicComponents projectName="p" />)

    await screen.findByText('D1')
    expect(screen.queryByLabelText('Height for LED_THT:LED_D1.8mm_W3.3mm_H2.4mm')).toBeNull()
  })
})
