import { describe, expect, it } from 'vitest'

import { storageChangeMessage } from './settings'

/** CTX-110.2. The warning that existed was honest and still failed:
 *
 *  > "New files will be saved to the new location once you restart. Anything
 *  > already saved stays at the old location and will not move automatically."
 *
 *  Every clause true. It describes FILES; the user's model is a LIST OF
 *  PROJECTS; nothing bridged the two. */
describe('storageChangeMessage', () => {
  const at = (root: string, projects: string[]) => ({ root, projects, count: projects.length })

  it('names the projects that will stop appearing', () => {
    /** The maintainer's real case: two projects under ~/Desktop, invisible
     *  after the root reverted to the app default. */
    const message = storageChangeMessage(
      at('/Users/k/Desktop', ['Hello Blinky', 'test 1']),
      at('/new', []),
    )

    expect(message).toContain('Hello Blinky, test 1')
    expect(message).toContain('will no longer appear')
    expect(message).toContain('These 2 projects')
  })

  it('uses the singular for one project', () => {
    const message = storageChangeMessage(at('/old', ['Only One']), at('/new', []))

    expect(message).toContain('This project is')
    expect(message).not.toContain('These 1 projects')
  })

  it('says the list will start empty when the new location has nothing', () => {
    const message = storageChangeMessage(at('/old', ['A']), at('/new', []))

    expect(message).toContain('start empty')
  })

  it('describes a swap, not an emptying, when the new location already has projects', () => {
    /** Pointing at a root that already holds projects is a change of list, not
     *  a loss of one -- and saying "your list will be empty" would be false. */
    const message = storageChangeMessage(at('/old', ['A']), at('/new', ['B', 'C']))

    expect(message).toContain('already holds 2 projects')
    expect(message).toContain('B, C')
    expect(message).not.toContain('start empty')
  })

  it('always says nothing is deleted, and that it is reversible', () => {
    /** The word a user brings to this is "lost". Being wrong in either
     *  direction is bad: believing files are gone costs trust, believing they
     *  are safe when they are not costs work. */
    const message = storageChangeMessage(at('/old', ['A']), at('/new', []))

    expect(message).toContain('Nothing is deleted')
    expect(message).toContain('brings those projects back')
  })

  it('does not list a hundred project names into a modal', () => {
    const many = Array.from({ length: 12 }, (_, i) => `project-${i}`)
    const message = storageChangeMessage(at('/old', many), at('/new', []))

    expect(message).toContain('and 9 more')
    expect(message).not.toContain('project-11')
  })

  it('says nothing about leaving projects behind when there are none', () => {
    /** A first move, from an empty default root, should not manufacture a
     *  warning about projects that do not exist. */
    const message = storageChangeMessage(at('/old', []), at('/new', ['A']))

    expect(message).not.toContain('will no longer appear')
    expect(message).toContain('already holds 1 project')
  })
})
